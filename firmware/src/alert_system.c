/*
 * alert_system.c
 * Multi-modal alert system: audio, haptic, and visual alerts
 */

#include "sentinelseye.h"
#include "alert_system.h"
#include <string.h>

/* ==================== ALERT AUDIO PATTERNS ==================== */

typedef struct {
    uint16_t freq_hz;
    uint16_t duration_ms;
    uint8_t volume;
} audio_note_t;

static const audio_note_t s_alert_tone_low[] = {
    { 440, 200, 40 },   /* A4 */
    { 0,    100, 0  },
    { 440, 200, 40 },
    { 0,    200, 0  }
};

static const audio_note_t s_alert_tone_medium[] = {
    { 660, 150, 60 },   /* E5 */
    { 0,    100, 0  },
    { 660, 150, 60 },
    { 0,    100, 0  },
    { 880, 300, 70 }    /* A5 */
};

static const audio_note_t s_alert_tone_high[] = {
    { 880, 100, 70 },   /* A5 */
    { 0,     50, 0  },
    { 880, 100, 70 },
    { 0,     50, 0  },
    { 880, 100, 70 },
    { 0,     50, 0  },
    { 1100, 400, 100 }  /* C#6 */
};

static const audio_note_t s_alert_ready_tone[] = {
    { 523,  150, 50 },  /* C5 */
    { 659,  150, 50 },  /* E5 */
    { 784,  150, 50 },  /* G5 */
    { 1047, 300, 60 }   /* C6 */
};

static const audio_note_t s_alert_error_tone[] = {
    { 200, 300, 80 },   /* Low buzz */
    { 0,    100, 0  },
    { 150, 400, 100 }   /* Lower buzz */
};

/* ==================== ALERT STATE ==================== */

static alert_system_state_t s_alert_state;
static QueueHandle_t s_alert_queue = NULL;
static TaskHandle_t s_alert_task_handle = NULL;
static TimerHandle_t s_cooldown_timer = NULL;
static uint32_t s_alert_level_counts[ALERT_LEVEL_HIGH + 1];
static bool s_alert_cooldown_active;
static int64_t s_last_alert_us;

/* ==================== AUDIO PLAYBACK ==================== */

static esp_err_t play_note(const audio_note_t *note) {
    if (!note || note->freq_hz == 0) {
        return ESP_OK;
    }

    i2s_set_clk(PIN_I2S_PORT, note->freq_hz, I2S_BITS_PER_SAMPLE_16BIT,
                I2S_CHANNEL_FMT_ONLY_LEFT);

    size_t bytes_written = 0;
    int16_t samples[256];
    float phase = 0.0f;
    float phase_inc = (2.0f * M_PI * note->freq_hz) / (float)note->freq_hz;

    for (int i = 0; i < 256; i++) {
        samples[i] = (int16_t)(sinf(phase) * (note->volume * 100));
        phase += phase_inc;
        if (phase > 2.0f * M_PI) phase -= 2.0f * M_PI;
    }

    return i2s_write(PIN_I2S_PORT, samples, sizeof(samples),
                     &bytes_written, pdMS_TO_TICKS(100));
}

static esp_err_t play_alert_pattern(const audio_note_t *pattern, int num_notes) {
    int i;

    if (!pattern || num_notes <= 0) {
        return ESP_ERR_INVALID_ARG;
    }

    for (i = 0; i < num_notes; i++) {
        esp_err_t ret = play_note(&pattern[i]);
        if (ret != ESP_OK) {
            return ret;
        }
        if (pattern[i].duration_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(pattern[i].duration_ms));
        }
    }

    return ESP_OK;
}

/* ==================== HAPTIC FEEDBACK ==================== */

static esp_err_t haptic_pulse(uint16_t duration_ms, uint8_t strength) {
    if (strength == 0 || duration_ms == 0) {
        return ESP_OK;
    }

    /* DRV2605: PWM duty cycle controls strength */
    gpio_set_level(PIN_HAPTIC_EN, 1);

    /* Use LEDC PWM for haptic strength control */
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0,
                  (strength * 1023) / 100);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    vTaskDelay(pdMS_TO_TICKS(duration_ms));

    gpio_set_level(PIN_HAPTIC_EN, 0);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    return ESP_OK;
}

static esp_err_t haptic_pattern(const haptic_pattern_t *pattern, int count) {
    int i;
    for (i = 0; i < count; i++) {
        if (pattern[i].duration_ms > 0) {
            haptic_pulse(pattern[i].duration_ms, pattern[i].strength);
            if (pattern[i].delay_ms > 0) {
                vTaskDelay(pdMS_TO_TICKS(pattern[i].delay_ms));
            }
        }
    }
    return ESP_OK;
}

/* ==================== LED INDICATORS ==================== */

static esp_err_t led_set_alert_level(uint8_t level) {
    switch (level) {
        case ALERT_LEVEL_LOW:
            gpio_set_level(PIN_STATUS_LED, 1);
            gpio_set_level(PIN_ALERT_LED, 0);
            break;
        case ALERT_LEVEL_MEDIUM:
            gpio_set_level(PIN_STATUS_LED, 1);
            gpio_set_level(PIN_ALERT_LED, 1);
            break;
        case ALERT_LEVEL_HIGH:
            gpio_set_level(PIN_STATUS_LED, 0);
            gpio_set_level(PIN_ALERT_LED, 1);
            break;
        default:
            break;
    }
    return ESP_OK;
}

/* ==================== ALERT COOLDOWN ==================== */

static void alert_cooldown_callback(TimerHandle_t timer) {
    (void)timer;
    s_alert_cooldown_active = false;
    ESP_LOGI("ALERT", "Cooldown period ended, alerts re-enabled");
}

/* ==================== ALERT TASK ==================== */

static void alert_task(void *pvParameters) {
    (void)pvParameters;
    alert_message_t alert;

    ESP_LOGI("ALERT", "Alert system task started");

    while (1) {
        if (xQueueReceive(s_alert_queue, &alert,
                          pdMS_TO_TICKS(1000)) == pdTRUE) {
            ESP_LOGW("ALERT", "=== ALERT ===");
            ESP_LOGW("ALERT", "Type: %d | Level: %d | Msg: %s",
                     alert.type, alert.level, alert.message);

            if (s_alert_cooldown_active) {
                ESP_LOGI("ALERT", "Alert in cooldown, deferring");
                continue;
            }

            s_alert_state.active_alerts++;
            s_alert_level_counts[alert.level]++;
            s_last_alert_us = esp_timer_get_time();

            /* Multi-modal alert */
            led_set_alert_level(alert.level);

            switch (alert.level) {
                case ALERT_LEVEL_LOW:
                    play_alert_pattern(s_alert_tone_low,
                                       sizeof(s_alert_tone_low) / sizeof(audio_note_t));
                    break;
                case ALERT_LEVEL_MEDIUM:
                    play_alert_pattern(s_alert_tone_medium,
                                       sizeof(s_alert_tone_medium) / sizeof(audio_note_t));
                    break;
                case ALERT_LEVEL_HIGH:
                    play_alert_pattern(s_alert_tone_high,
                                       sizeof(s_alert_tone_high) / sizeof(audio_note_t));
                    break;
            }

            haptic_pulse(ALERT_HAPTIC_DURATION_MS, ALERT_HAPTIC_STRENGTH);

            /* Start cooldown */
            s_alert_cooldown_active = true;
            xTimerChangePeriod(s_cooldown_timer, pdMS_TO_TICKS(3000), 0);
            xTimerStart(s_cooldown_timer, 0);

            ESP_LOGW("ALERT", "Alert processed");
        }

        /* Check for persistent high-level alerts */
        if (s_alert_level_counts[ALERT_LEVEL_HIGH] > 3) {
            ESP_LOGE("ALERT", "Critical alert threshold exceeded! Initiating emergency alert");
            led_set_alert_level(ALERT_LEVEL_HIGH);
            play_alert_pattern(s_alert_tone_high,
                               sizeof(s_alert_tone_high) / sizeof(audio_note_t));
            haptic_pulse(1000, 100);
            sentinelseye_handle_alert(ALERT_DROWSINESS_HIGH, ALERT_LEVEL_HIGH,
                                       "Emergency alert: 3+ critical alerts");
            s_alert_level_counts[ALERT_LEVEL_HIGH] = 0;
        }
    }
}

/* ==================== PUBLIC API ==================== */

esp_err_t alert_system_init(void) {
    esp_err_t ret;

    ESP_LOGI("ALERT", "Initializing alert system...");

    memset(&s_alert_state, 0, sizeof(s_alert_state));
    s_alert_state.initialized = true;
    s_alert_cooldown_active = false;

    /* Create alert queue */
    s_alert_queue = xQueueCreate(ALERT_QUEUE_LEN, sizeof(alert_message_t));
    if (!s_alert_queue) {
        ESP_LOGE("ALERT", "Alert queue creation FAILED");
        return ESP_ERR_NO_MEM;
    }

    /* Create cooldown timer */
    s_cooldown_timer = xTimerCreate("alert_cooldown", pdMS_TO_TICKS(3000),
                                     pdFALSE, NULL, alert_cooldown_callback);
    if (!s_cooldown_timer) {
        ESP_LOGE("ALERT", "Cooldown timer creation FAILED");
        return ESP_ERR_NO_MEM;
    }

    /* Initialize LEDC PWM for haptic */
    ledc_timer_config_t ledc_timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = LEDC_TIMER_0,
        .duty_resolution = LEDC_TIMER_10_BIT,
        .freq_hz = 500,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ret = ledc_timer_config(&ledc_timer);
    if (ret != ESP_OK) {
        ESP_LOGW("ALERT", "LEDC timer config FAILED: %d", ret);
    }

    ledc_channel_config_t ledc_channel = {
        .gpio_num = PIN_HAPTIC_PWM,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0
    };
    ret = ledc_channel_config(&ledc_channel);
    if (ret != ESP_OK) {
        ESP_LOGW("ALERT", "LEDC channel config FAILED: %d", ret);
    }

    ESP_LOGI("ALERT", "Alert system initialized");
    return ESP_OK;
}

esp_err_t alert_system_queue_alert(alert_type_t type, uint8_t level,
                                    const char *message) {
    alert_message_t alert;

    if (!message || !s_alert_queue) {
        return ESP_ERR_INVALID_ARG;
    }

    memset(&alert, 0, sizeof(alert));
    alert.type = type;
    alert.level = level;
    alert.timestamp_us = esp_timer_get_time();
    alert.device_id = g_device.device_id;
    strncpy(alert.message, message, ALERT_MSG_BUFFER_SIZE - 1);

    if (xQueueSend(s_alert_queue, &alert, pdMS_TO_TICKS(100)) != pdTRUE) {
        ESP_LOGW("ALERT", "Alert queue FULL, dropping alert");
        return ESP_ERR_NO_MEM;
    }

    g_device.alert_counter++;
    return ESP_OK;
}

esp_err_t alert_system_process_inference(inference_result_t result,
                                          float confidence) {
    alert_type_t alert_type = ALERT_EYE_CLOSED;
    uint8_t level = ALERT_LEVEL_LOW;
    char message[ALERT_MSG_BUFFER_SIZE];

    switch (result) {
        case INFERENCE_RESULT_AWAKE:
            return ESP_OK;
        case INFERENCE_RESULT_DROWSY:
            alert_type = ALERT_DROWSINESS_LOW;
            level = ALERT_LEVEL_MEDIUM;
            snprintf(message, ALERT_MSG_BUFFER_SIZE,
                     "DROWSINESS DETECTED - Confidence: %.0f%%", confidence * 100.0f);
            break;
        case INFERENCE_RESULT_ASLEEP:
            alert_type = ALERT_DROWSINESS_HIGH;
            level = ALERT_LEVEL_HIGH;
            snprintf(message, ALERT_MSG_BUFFER_SIZE,
                     "EYES CLOSED - WAKE UP! Confidence: %.0f%%", confidence * 100.0f);
            break;
        default:
            return ESP_ERR_INVALID_ARG;
    }

    return alert_system_queue_alert(alert_type, level, message);
}

esp_err_t alert_system_play_ready_tone(void) {
    return play_alert_pattern(s_alert_ready_tone,
                              sizeof(s_alert_ready_tone) / sizeof(audio_note_t));
}

esp_err_t alert_system_play_error_tone(void) {
    return play_alert_pattern(s_alert_error_tone,
                              sizeof(s_alert_error_tone) / sizeof(audio_note_t));
}

void alert_system_print_status(void) {
    ESP_LOGI("ALERT", "Status: active=%u, low=%u, med=%u, high=%u",
             s_alert_state.active_alerts,
             s_alert_level_counts[ALERT_LEVEL_LOW],
             s_alert_level_counts[ALERT_LEVEL_MEDIUM],
             s_alert_level_counts[ALERT_LEVEL_HIGH]);
}

const alert_system_state_t *alert_system_get_state(void) {
    return &s_alert_state;
}
