/*
 * sentinelseye.h
 * SentinelEye main header file
 * AI-Powered Wearable Drowsiness Detection System
 */

#ifndef SENTINELEY_H
#define SENTINELEY_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <driver/i2s.h>
#include <esp_camera.h>
#include <esp_wifi.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <nvs_flash.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <driver/gpio.h>
#include <driver/i2c.h>
#include <esp_pm.h>
#include <esp_sleep.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== SYSTEM CONFIGURATION ==================== */

#define SENTINELEY_VERSION        "1.0.0"
#define SENTINELEY_FIRMWARE_BUILD __DATE__ " " __TIME__

/* Device Configuration */
#define DEVICE_NAME               "SentinelEye-S1"
#define DEVICE_MANUFACTURER       "SentinelEye Defense Systems"
#define DEVICE_MODEL              "SE-ESP32S3"

/* Hardware Pins */
#define PIN_CAMERA_PWDN           GPIO_NUM_32
#define PIN_CAMERA_RESET          GPIO_NUM_33
#define PIN_CAMERA_XCLK           GPIO_NUM_34
#define PIN_CAMERA_SIOD           GPIO_NUM_35
#define PIN_CAMERA_SIOC           GPIO_NUM_36
#define PIN_CAMERA_D7             GPIO_NUM_37
#define PIN_CAMERA_D6             GPIO_NUM_38
#define PIN_CAMERA_D5             GPIO_NUM_39
#define PIN_CAMERA_D4             GPIO_NUM_40
#define PIN_CAMERA_D3             GPIO_NUM_41
#define PIN_CAMERA_D2             GPIO_NUM_42
#define PIN_CAMERA_D1             GPIO_NUM_43
#define PIN_CAMERA_D0             GPIO_NUM_44
#define PIN_CAMERA_VSYNC          GPIO_NUM_45
#define PIN_CAMERA_HREF           GPIO_NUM_46
#define PIN_CAMERA_PCLK           GPIO_NUM_47

#define PIN_I2C_SDA               GPIO_NUM_8
#define PIN_I2C_SCL               GPIO_NUM_9
#define PIN_I2C_PORT              I2C_NUM_0

#define PIN_I2S_BCLK              GPIO_NUM_4
#define PIN_I2S_LRCLK             GPIO_NUM_5
#define PIN_I2S_DIN               GPIO_NUM_6
#define PIN_I2S_PORT              I2S_NUM_0

#define PIN_HAPTIC_EN             GPIO_NUM_10
#define PIN_HAPTIC_PWM            GPIO_NUM_11
#define PIN_STATUS_LED            GPIO_NUM_12
#define PIN_ALERT_LED             GPIO_NUM_13
#define PIN_RESET_BUTTON          GPIO_NUM_14
#define PIN_USB_DP                GPIO_NUM_15
#define PIN_USB_DN                GPIO_NUM_16

/* Camera Configuration */
#define CAMERA_WIDTH              240
#define CAMERA_HEIGHT             240
#define CAMERA_FORMAT             PIXFORMAT_RGB565
#define CAMERA_FPS                15
#define CAMERA_QUALITY            10
#define CAMERA_XCLK_FREQ          20000000

/* Inference Configuration */
#define INFERENCE_INTERVAL_MS     1000
#define EYE_CLOSED_THRESHOLD      0.55
#define DROWSINESS_THRESHOLD      0.60
#define CONSECUTIVE_FRAMES        3

/* Alert Configuration */
#define ALERT_LEVEL_LOW           1
#define ALERT_LEVEL_MEDIUM        2
#define ALERT_LEVEL_HIGH          3
#define ALERT_AUDIO_PATTERN       "low_med_high"
#define ALERT_HAPTIC_DURATION_MS  500
#define ALERT_HAPTIC_STRENGTH     80

/* Power Management */
#define BATTERY_LOW_VOLTAGE       3400
#define BATTERY_CRITICAL_VOLTAGE  3200
#define DEEP_SLEEP_TIMEOUT_S      3600
#define CPU_FREQ_HIGH             240
#define CPU_FREQ_LOW              80

/* Network Configuration */
#define SENTINELEY_WIFI_SSID      "SentinelEye-Command"
#define SENTINELEY_WIFI_PASS      "SecureComms2026!"
#define SENTINELEY_SERVER_IP      "192.168.4.1"
#define SENTINELEY_SERVER_PORT    8443

/* Queue Configuration */
#define INFERENCE_QUEUE_LEN       5
#define ALERT_QUEUE_LEN           10
#define SENSOR_QUEUE_LEN          5

/* Neural Network Configuration */
#define NN_INPUT_WIDTH            24
#define NN_INPUT_HEIGHT           24
#define NN_INPUT_CHANNELS         3
#define NN_NUM_CLASSES            3
#define NN_MODEL_SIZE             4096
#define NN_TENSOR_ARENA_SIZE      20000
#define NN_CONFIDENCE_THRESHOLD   0.75

/* Task Priorities */
#define TASK_PRIORITY_CAMERA      5
#define TASK_PRIORITY_INFERENCE   4
#define TASK_PRIORITY_ALERT       3
#define TASK_PRIORITY_NETWORK     2
#define TASK_PRIORITY_POWER       1

/* Task Stack Sizes */
#define STACK_SIZE_CAMERA         8192
#define STACK_SIZE_INFERENCE      12288
#define STACK_SIZE_ALERT          4096
#define STACK_SIZE_NETWORK        8192
#define STACK_SIZE_POWER          4096

/* Buffer Sizes */
#define CAMERA_FRAME_BUFFER_SIZE  (CAMERA_WIDTH * CAMERA_HEIGHT * 2)
#define NN_INPUT_BUFFER_SIZE      (NN_INPUT_WIDTH * NN_INPUT_HEIGHT * NN_INPUT_CHANNELS)
#define ALERT_MSG_BUFFER_SIZE     256

/* Timing Configuration */
#define SYSTEM_TICK_MS            10
#define STATUS_REPORT_INTERVAL_MS 5000
#define HEARTBEAT_INTERVAL_MS     30000
#define OTA_CHECK_INTERVAL_MS     600000

/* Alert Messages */
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

/* Inference Results */
typedef enum {
    INFERENCE_RESULT_AWAKE = 0,
    INFERENCE_RESULT_DROWSY,
    INFERENCE_RESULT_ASLEEP
} inference_result_t;

/* System State */
typedef enum {
    SYSTEM_STATE_INIT = 0,
    SYSTEM_STATE_ACTIVE,
    SYSTEM_STATE_LOW_POWER,
    SYSTEM_STATE_DEEP_SLEEP,
    SYSTEM_STATE_ERROR
} system_state_t;

/* Inference Output Structure */
typedef struct {
    inference_result_t result;
    float confidence;
    float eye_openness;
    uint32_t frame_number;
    int64_t timestamp_us;
    uint8_t consecutive_drowsy_frames;
} inference_output_t;

/* Alert Message Structure */
typedef struct {
    alert_type_t type;
    uint8_t level;
    char message[ALERT_MSG_BUFFER_SIZE];
    int64_t timestamp_us;
    uint32_t device_id;
} alert_message_t;

/* Battery Status Structure */
typedef struct {
    float voltage;
    float current;
    float soc_percent;
    bool charging;
    bool low_battery;
    bool critical_battery;
} battery_status_t;

/* Network Status Structure */
typedef struct {
    bool wifi_connected;
    bool ble_advertising;
    bool server_reachable;
    uint32_t packets_sent;
    uint32_t packets_received;
    uint32_t connection_uptime_s;
} network_status_t;

/* Main Device State Structure */
typedef struct {
    system_state_t state;
    uint32_t device_id;
    char firmware_version[32];
    char build_timestamp[32];
    uint32_t frame_counter;
    uint32_t inference_counter;
    uint32_t alert_counter;
    uint64_t total_uptime_us;
    uint32_t frames_processed;
    uint32_t drowsy_frames_detected;
    float avg_inference_time_us;
    battery_status_t battery;
    network_status_t network;
    SemaphoreHandle_t inference_mutex;
    QueueHandle_t inference_queue;
    QueueHandle_t alert_queue;
    TaskHandle_t camera_task_handle;
    TaskHandle_t inference_task_handle;
    TaskHandle_t alert_task_handle;
    TaskHandle_t network_task_handle;
    TaskHandle_t power_task_handle;
} device_state_t;

/* Global state */
extern device_state_t g_device;

/* Public API */
esp_err_t sentinelseye_system_init(void);
esp_err_t sentinelseye_camera_init(void);
esp_err_t sentinelseye_alert_system_init(void);
esp_err_t sentinelseye_network_init(void);
esp_err_t sentinelseye_power_mgmt_init(void);
esp_err_t sentinelseye_inference_init(void);
esp_err_t sentinelseye_nn_init(void);

void sentinelseye_main_loop(void);
void sentinelseye_enter_sleep(void);
void sentinelseye_handle_alert(alert_type_t type, uint8_t level, const char *msg);

#ifdef __cplusplus
}
#endif

#endif /* SENTINELEY_H */
