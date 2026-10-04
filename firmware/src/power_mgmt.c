/*
 * power_mgmt.c
 * Battery monitoring, power optimization, and sleep management
 */

#include "sentinelseye.h"
#include "power_mgmt.h"
#include <string.h>

/* ==================== POWER STATE ==================== */

static power_mgmt_state_t s_power_state;
static TaskHandle_t s_power_task_handle = NULL;
static esp_timer_handle_t s_battery_timer = NULL;
static float s_voltage_samples[10];
static int s_voltage_sample_index;
static bool s_sleep_enabled;
static int64_t s_last_activity_us;

/* ==================== VOLTAGE SAMPLING ==================== */

static esp_err_t read_battery_voltage(float *voltage) {
    esp_err_t ret;
    int adc_raw;
    float adc_voltage;

    if (!voltage) {
        return ESP_ERR_INVALID_ARG;
    }

    /* ADC1 channel 6 (GPIO34) connected to battery via voltage divider */
    ret = adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_ATTEN_DB_11);
    if (ret != ESP_OK) {
        return ret;
    }

    adc_raw = adc1_get_raw(ADC1_CHANNEL_6);
    if (adc_raw < 0) {
        return ESP_ERR_INVALID_RESPONSE;
    }

    /* Convert: 150k / 330k divider, Vref=1100mV, 12-bit ADC */
    adc_voltage = (float)adc_raw * 1100.0f / 4095.0f;
    *voltage = adc_voltage * (150.0f + 330.0f) / 150.0f;

    return ESP_OK;
}

static esp_err_t read_charging_current(float *current_ma) {
    /* INA219-style current sensing via ADC */
    esp_err_t ret;
    int adc_raw;
    float adc_voltage;

    if (!current_ma) {
        return ESP_ERR_INVALID_ARG;
    }

    ret = adc1_config_channel_atten(ADC1_CHANNEL_7, ADC_ATTEN_DB_11);
    if (ret != ESP_OK) {
        *current_ma = 0.0f;
        return ret;
    }

    adc_raw = adc1_get_raw(ADC1_CHANNEL_7);
    adc_voltage = (float)adc_raw * 1100.0f / 4095.0f;

    /* INA219: 100mV/A shunt, gain=8 -> 8mV/A, current = Vshunt / 0.008 */
    *current_ma = adc_voltage / 8.0f * 1000.0f;

    return ESP_OK;
}

static float compute_soc(float voltage) {
    /* LiPo discharge curve approximation */
    if (voltage > 4200.0f) return 100.0f;
    if (voltage > 4150.0f) return 95.0f + (voltage - 4150.0f) * 0.2f;
    if (voltage > 4100.0f) return 90.0f + (voltage - 4100.0f) * 0.1f;
    if (voltage > 4000.0f) return 75.0f + (voltage - 4000.0f) * 0.15f;
    if (voltage > 3900.0f) return 60.0f + (voltage - 3900.0f) * 0.15f;
    if (voltage > 3800.0f) return 45.0f + (voltage - 3800.0f) * 0.15f;
    if (voltage > 3700.0f) return 30.0f + (voltage - 3700.0f) * 0.15f;
    if (voltage > 3600.0f) return 15.0f + (voltage - 3600.0f) * 0.15f;
    if (voltage > 3500.0f) return 5.0f + (voltage - 3500.0f) * 0.1f;
    if (voltage > 3400.0f) return 0.0f + (voltage - 3400.0f) * 0.05f;
    return 0.0f;
}

static float lowpass_filter(float new_sample, float *history, int history_len) {
    float sum = 0.0f;
    int i;
    for (i = 0; i < history_len - 1; i++) {
        history[i] = history[i + 1];
        sum += history[i];
    }
    history[history_len - 1] = new_sample;
    sum += new_sample;
    return sum / (float)history_len;
}

/* ==================== BATTERY MONITOR TASK ==================== */

static void battery_monitor_timer_callback(void *arg) {
    (void)arg;
    float voltage, current_ma;

    esp_err_t ret = read_battery_voltage(&voltage);
    if (ret != ESP_OK) {
        ESP_LOGE("POWER", "Failed to read battery voltage: %d", ret);
        return;
    }

    ret = read_charging_current(&current_ma);
    if (ret != ESP_OK) {
        current_ma = 0.0f;
    }

    /* Low-pass filter voltage */
    float filtered_voltage = lowpass_filter(voltage, s_voltage_samples, 10);

    /* Update state */
    s_power_state.battery.voltage = filtered_voltage;
    s_power_state.battery.current = current_ma;
    s_power_state.battery.soc_percent = compute_soc(filtered_voltage);
    s_power_state.battery.charging = (current_ma < -50.0f);

    /* Threshold checks */
    if (filtered_voltage < BATTERY_CRITICAL_VOLTAGE) {
        if (!s_power_state.battery.critical_battery) {
            ESP_LOGE("POWER", "CRITICAL BATTERY: %.0fmV", filtered_voltage);
            sentinelseye_handle_alert(ALERT_CRITICAL_BATTERY, ALERT_LEVEL_HIGH,
                                       "CRITICAL BATTERY - Shutdown imminent");
            s_power_state.battery.critical_battery = true;
        }
        s_power_state.battery.low_battery = true;
    } else if (filtered_voltage < BATTERY_LOW_VOLTAGE) {
        if (!s_power_state.battery.low_battery) {
            ESP_LOGW("POWER", "LOW BATTERY: %.0fmV", filtered_voltage);
            sentinelseye_handle_alert(ALERT_LOW_BATTERY, ALERT_LEVEL_MEDIUM,
                                       "Low battery - Connect charger");
            s_power_state.battery.low_battery = true;
        }
    } else {
        s_power_state.battery.low_battery = false;
        s_power_state.battery.critical_battery = false;
    }

    /* Update power state */
    s_power_state.last_voltage_us = esp_timer_get_time();
}

/* ==================== POWER MANAGEMENT TASK ==================== */

static void power_task(void *pvParameters) {
    (void)pvParameters;

    ESP_LOGI("POWER", "Power management task started");

    while (1) {
        /* Check if we should enter low-power mode */
        int64_t now = esp_timer_get_time();
        int64_t idle_time = now - s_last_activity_us;

        if (idle_time > DEEP_SLEEP_TIMEOUT_S * 1000000LL) {
            ESP_LOGI("POWER", "Entering deep sleep after %ds idle",
                     (int)(idle_time / 1000000));
            s_power_state.state = POWER_STATE_DEEP_SLEEP;
            power_mgmt_enter_deep_sleep();
        }

        /* Adaptive CPU frequency */
        if (s_power_state.battery.soc_percent < 15.0f && g_device.state == SYSTEM_STATE_ACTIVE) {
            ESP_LOGI("POWER", "Low battery: reducing CPU frequency to %dMHz", CPU_FREQ_LOW);
            esp_pm_config_t pm_config = {
                .max_freq_mhz = CPU_FREQ_LOW,
                .min_freq_mhz = CPU_FREQ_LOW,
                .light_sleep_enable = true
            };
            esp_pm_configure(&pm_config);
            s_power_state.cpu_freq_mhz = CPU_FREQ_LOW;
        } else if (s_power_state.battery.soc_percent > 20.0f && s_power_state.cpu_freq_mhz == CPU_FREQ_LOW) {
            ESP_LOGI("POWER", "Battery recovered: restoring CPU frequency to %dMHz", CPU_FREQ_HIGH);
            esp_pm_config_t pm_config = {
                .max_freq_mhz = CPU_FREQ_HIGH,
                .min_freq_mhz = CPU_FREQ_LOW,
                .light_sleep_enable = false
            };
            esp_pm_configure(&pm_config);
            s_power_state.cpu_freq_mhz = CPU_FREQ_HIGH;
        }

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

/* ==================== PUBLIC API ==================== */

esp_err_t power_mgmt_init(void) {
    esp_err_t ret;

    ESP_LOGI("POWER", "Initializing power management...");

    memset(&s_power_state, 0, sizeof(s_power_state));
    s_power_state.state = POWER_STATE_NORMAL;
    s_power_state.cpu_freq_mhz = CPU_FREQ_HIGH;
    s_power_state.charging = false;
    s_power_state.saved_fps = CAMERA_FPS;
    s_sleep_enabled = true;
    s_last_activity_us = esp_timer_get_time();

    /* Initialize ADC */
    ret = adc1_init();
    if (ret != ESP_OK) {
        ESP_LOGW("POWER", "ADC init FAILED: %d", ret);
        return ret;
    }

    /* Create battery monitoring timer */
    const esp_timer_create_args_t timer_args = {
        .callback = battery_monitor_timer_callback,
        .arg = NULL,
        .name = "battery_timer"
    };
    ret = esp_timer_create(&timer_args, &s_battery_timer);
    if (ret != ESP_OK) {
        ESP_LOGW("POWER", "Battery timer creation FAILED: %d", ret);
        return ret;
    }

    /* Start periodic battery monitoring */
    esp_timer_start_periodic(s_battery_timer, 1000000); /* 1 second */

    /* Create power management task */
    xTaskCreate(power_task, "power_task", STACK_SIZE_POWER, NULL,
                TASK_PRIORITY_POWER, &s_power_task_handle);

    ESP_LOGI("POWER", "Power management initialized");

    /* Do initial voltage reading */
    battery_monitor_timer_callback(NULL);

    return ESP_OK;
}

esp_err_t power_mgmt_enter_deep_sleep(void) {
    ESP_LOGI("POWER", "Entering deep sleep mode...");

    /* Disable WiFi and BT */
    esp_wifi_stop();
    esp_bt_controller_disable();

    /* Save critical state */
    // TODO: Save to NVS

    /* Configure wakeup source: GPIO button */
    gpio_wakeup_enable(PIN_RESET_BUTTON, GPIO_INTR_LOW_LEVEL);
    esp_sleep_enable_gpio_wakeup();

    /* Configure timer wakeup (periodic wake for status check) */
    esp_sleep_enable_timer_wakeup(60000000); /* 60 seconds */

    ESP_LOGI("POWER", "Entering deep sleep...");
    vTaskDelay(pdMS_TO_TICKS(100));

    esp_deep_sleep_start();

    return ESP_OK;
}

esp_err_t power_mgmt_enter_light_sleep(void) {
    if (!s_sleep_enabled) {
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI("POWER", "Entering light sleep...");

    esp_pm_config_t pm_config = {
        .max_freq_mhz = CPU_FREQ_LOW,
        .min_freq_mhz = CPU_FREQ_LOW,
        .light_sleep_enable = true
    };
    esp_pm_configure(&pm_config);
    s_power_state.state = POWER_STATE_LIGHT_SLEEP;

    return ESP_OK;
}

esp_err_t power_mgmt_exit_sleep(void) {
    ESP_LOGI("POWER", "Exiting sleep mode...");

    s_sleep_enabled = true;
    s_last_activity_us = esp_timer_get_time();

    if (s_power_state.battery.soc_percent > 20.0f) {
        esp_pm_config_t pm_config = {
            .max_freq_mhz = CPU_FREQ_HIGH,
            .min_freq_mhz = CPU_FREQ_LOW,
            .light_sleep_enable = false
        };
        esp_pm_configure(&pm_config);
        s_power_state.cpu_freq_mhz = CPU_FREQ_HIGH;
    }

    s_power_state.state = POWER_STATE_NORMAL;

    return ESP_OK;
}

void power_mgmt_set_activity(void) {
    s_last_activity_us = esp_timer_get_time();
}

esp_err_t power_mgmt_get_status(power_mgmt_state_t *status) {
    if (!status) {
        return ESP_ERR_INVALID_ARG;
    }
    memcpy(status, &s_power_state, sizeof(power_mgmt_state_t));
    return ESP_OK;
}

float power_mgmt_get_battery_voltage(void) {
    return s_power_state.battery.voltage;
}

float power_mgmt_get_battery_soc(void) {
    return s_power_state.battery.soc_percent;
}

bool power_mgmt_is_charging(void) {
    return s_power_state.battery.charging;
}

int power_mgmt_get_estimated_runtime_minutes(void) {
    float soc = s_power_state.battery.soc_percent;
    float current_ma = fabsf(s_power_state.battery.current);

    if (current_ma < 1.0f) {
        current_ma = 150.0f; /* Average system draw */
    }

    float capacity_remaining = (soc / 100.0f) * 2000.0f; /* 2000mAh */
    float runtime_minutes = (capacity_remaining / current_ma) * 60.0f;

    return (int)runtime_minutes;
}

void power_mgmt_print_status(void) {
    ESP_LOGI("POWER", "State=%d | V=%.0fmV | SOC=%.0f%% | I=%.0fmA | Charging=%d | CPU=%dMHz",
             s_power_state.state,
             s_power_state.battery.voltage,
             s_power_state.battery.soc_percent,
             s_power_state.battery.current,
             s_power_state.battery.charging,
             s_power_state.cpu_freq_mhz);
    ESP_LOGI("POWER", "Estimated runtime: %d minutes",
             power_mgmt_get_estimated_runtime_minutes());
}
