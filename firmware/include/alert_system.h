#ifndef ALERT_SYSTEM_H
#define ALERT_SYSTEM_H

#include "sentinelseye.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Alert Configuration */
#define ALERT_QUEUE_LEN           10
#define ALERT_HAPTIC_DURATION_MS  500
#define ALERT_HAPTIC_STRENGTH     80
#define ALERT_AUDIO_VOLUME        70
#define ALERT_COOLDOWN_MS         3000

/* Alert Types */
typedef enum {
    ALERT_EYE_CLOSED = 0,
    ALERT_DROWSINESS_LOW,
    ALERT_DROWSINESS_MEDIUM,
    ALERT_DROWSINESS_HIGH,
    ALERT_DISTRACTION,
    ALERT_SYSTEM_ERROR,
    ALERT_LOW_BATTERY,
    ALERT_CRITICAL_BATTERY
} alert_type_t;

/* Haptic Pattern */
typedef struct {
    uint16_t duration_ms;
    uint8_t strength;
    uint16_t delay_ms;
} haptic_pattern_t;

/* Alert System State */
typedef struct {
    bool initialized;
    uint32_t total_alerts_triggered;
    uint32_t active_alerts;
    uint32_t alerts_by_type[8];
    uint8_t alert_level_counts[ALERT_LEVEL_HIGH + 1];
    int64_t last_alert_us;
    bool audio_enabled;
    bool haptic_enabled;
    bool led_enabled;
} alert_system_state_t;

/* Initialization */
esp_err_t alert_system_init(void);

/* Queue Alerts */
esp_err_t alert_system_queue_alert(alert_type_t type, uint8_t level,
                                    const char *message);
esp_err_t alert_system_process_inference(inference_result_t result,
                                          float confidence);

/* Audio Feedback */
esp_err_t alert_system_play_ready_tone(void);
esp_err_t alert_system_play_error_tone(void);
esp_err_t alert_system_play_alert_tone(uint8_t level);

/* Haptic Feedback */
esp_err_t alert_system_pulse_haptic(uint16_t duration_ms, uint8_t strength);

/* LED Feedback */
esp_err_t alert_system_set_led(uint8_t red, uint8_t green);

/* State */
const alert_system_state_t *alert_system_get_state(void);
void alert_system_print_status(void);
esp_err_t alert_system_enable_audio(bool enable);
esp_err_t alert_system_enable_haptic(bool enable);
esp_err_t alert_system_enable_led(bool enable);

#ifdef __cplusplus
}
#endif

#endif /* ALERT_SYSTEM_H */
