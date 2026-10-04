#ifndef POWER_MGMT_H
#define POWER_MGMT_H

#include "sentinelseye.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Power States */
typedef enum {
    POWER_STATE_NORMAL = 0,
    POWER_STATE_LOW_POWER,
    POWER_STATE_LIGHT_SLEEP,
    POWER_STATE_DEEP_SLEEP,
    POWER_STATE_CHARGING
} power_state_t;

/* Battery Status */
typedef struct {
    float voltage;
    float current;
    float soc_percent;
    bool charging;
    bool low_battery;
    bool critical_battery;
} battery_status_t;

/* Power Management State */
typedef struct {
    power_state_t state;
    battery_status_t battery;
    int cpu_freq_mhz;
    uint32_t saved_fps;
    int64_t last_voltage_us;
} power_mgmt_state_t;

/* Initialization */
esp_err_t power_mgmt_init(void);
esp_err_t adc1_init(void);

/* Sleep Management */
esp_err_t power_mgmt_enter_deep_sleep(void);
esp_err_t power_mgmt_enter_light_sleep(void);
esp_err_t power_mgmt_exit_sleep(void);
void power_mgmt_set_activity(void);

/* Status */
esp_err_t power_mgmt_get_status(power_mgmt_state_t *status);
float power_mgmt_get_battery_voltage(void);
float power_mgmt_get_battery_soc(void);
bool power_mgmt_is_charging(void);
int power_mgmt_get_estimated_runtime_minutes(void);
void power_mgmt_print_status(void);

#ifdef __cplusplus
}
#endif

#endif /* POWER_MGMT_H */
