#include "sentinelseye.h"
#include "eye_detection.h"
#include "tflite_inference.h"
#include "alert_system.h"
#include "power_mgmt.h"

/* Global device state */
device_state_t g_device;

/* RTOS handles */
static TaskHandle_t g_init_task_handle = NULL;

/* Prototypes */
static void main_init_task(void *pvParameters);
static void system_status_report_task(void *pvParameters);
static esp_err_t system_self_test(void);

/*
 * Main entry point
 */
void app_main(void) {
    ESP_LOGI("SENTINELEY", "Booting %s v%s", DEVICE_NAME, SENTINELEY_VERSION);
    ESP_LOGI("SENTINELEY", "Build: %s", SENTINELEY_FIRMWARE_BUILD);
    ESP_LOGI("SENTINELEY", "ESP32-S3 D0WDQ6 chip rev %d", esp_chip_info_get_chip_ver());

    /* Create main init task */
    xTaskCreate(main_init_task, "init_task", STACK_SIZE_CAMERA, NULL,
                TASK_PRIORITY_CAMERA, &g_init_task_handle);
}

/*
 * Main initialization task
 */
static void main_init_task(void *pvParameters) {
    esp_err_t ret;

    ESP_LOGI("SENTINELEY", "=== System Initialization Starting ===");

    /* Initialize NVS flash */
    ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI("SENTINELEY", "NVS initialized");

    /* Initialize I2C bus */
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = PIN_I2C_SDA,
        .scl_io_num = PIN_I2C_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = 400000
    };
    ESP_ERROR_CHECK(i2c_param_config(PIN_I2C_PORT, &conf));
    ESP_ERROR_CHECK(i2c_driver_install(PIN_I2C_PORT, conf.mode, 0, 0, 0));
    ESP_LOGI("SENTINELEY", "I2C initialized");

    /* Initialize I2S for audio */
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 64,
        .use_apll = false,
        .tx_desc_auto_clear = true
    };
    i2s_pin_config_t pin_config = {
        .bck_io_num = PIN_I2S_BCLK,
        .ws_io_num = PIN_I2S_LRCLK,
        .data_out_num = PIN_I2S_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    ESP_ERROR_CHECK(i2s_driver_install(PIN_I2S_PORT, &i2s_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(PIN_I2S_PORT, &pin_config));
    ESP_LOGI("SENTINELEY", "I2S initialized");

    /* Initialize GPIO */
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_STATUS_LED) | (1ULL << PIN_ALERT_LED) |
                       (1ULL << PIN_HAPTIC_EN) | (1ULL << PIN_RESET_BUTTON),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf);
    gpio_set_level(PIN_STATUS_LED, 1);
    gpio_set_level(PIN_ALERT_LED, 0);
    ESP_LOGI("SENTINELEY", "GPIO initialized");

    /* Run self-test */
    ret = system_self_test();
    if (ret != ESP_OK) {
        ESP_LOGE("SENTINELEY", "Self-test FAILED! Code: %d", ret);
        sentinelseye_handle_alert(ALERT_SYSTEM_ERROR, ALERT_LEVEL_HIGH,
                                   "Self-test failed");
        vTaskDelay(pdMS_TO_TICKS(5000));
        esp_restart();
    }
    ESP_LOGI("SENTINELEY", "Self-test PASSED");

    /* Initialize subsystems */
    g_device.state = SYSTEM_STATE_INIT;

    ESP_LOGI("SENTINELEY", "Initializing camera...");
    ret = sentinelseye_camera_init();
    if (ret != ESP_OK) {
        ESP_LOGE("SENTINELEY", "Camera init FAILED");
        sentinelseye_handle_alert(ALERT_SYSTEM_ERROR, ALERT_LEVEL_HIGH,
                                   "Camera init failed");
        goto error_recovery;
    }

    ESP_LOGI("SENTINELEY", "Initializing inference engine...");
    ret = sentinelseye_inference_init();
    if (ret != ESP_OK) {
        ESP_LOGE("SENTINELEY", "Inference init FAILED");
        sentinelseye_handle_alert(ALERT_SYSTEM_ERROR, ALERT_LEVEL_HIGH,
                                   "Inference init failed");
        goto error_recovery;
    }

    ESP_LOGI("SENTINELEY", "Initializing alert system...");
    ret = sentinelseye_alert_system_init();
    if (ret != ESP_OK) {
        ESP_LOGE("SENTINELEY", "Alert system init FAILED");
        goto error_recovery;
    }

    ESP_LOGI("SENTINELEY", "Initializing network...");
    ret = sentinelseye_network_init();
    if (ret != ESP_OK) {
        ESP_LOGW("SENTINELEY", "Network init FAILED (continuing offline)");
    }

    ESP_LOGI("SENTINELEY", "Initializing power management...");
    ret = sentinelseye_power_mgmt_init();
    if (ret != ESP_OK) {
        ESP_LOGW("SENTINELEY", "Power mgmt init FAILED (continuing)");
    }

    /* Set CPU frequency for inference */
    ESP_ERROR_CHECK(esp_pm_config_t pm_config = {
        .max_freq_mhz = CPU_FREQ_HIGH,
        .min_freq_mhz = CPU_FREQ_LOW,
        .light_sleep_enable = false
    });
    ESP_ERROR_CHECK(esp_pm_configure(&pm_config));

    /* Create task queues */
    g_device.inference_queue = xQueueCreate(INFERENCE_QUEUE_LEN, sizeof(inference_output_t));
    g_device.alert_queue = xQueueCreate(ALERT_QUEUE_LEN, sizeof(alert_message_t));
    g_device.inference_mutex = xSemaphoreCreateMutex();

    if (!g_device.inference_queue || !g_device.alert_queue || !g_device.inference_mutex) {
        ESP_LOGE("SENTINELEY", "Queue/mutex creation FAILED");
        goto error_recovery;
    }

    /* Create worker tasks */
    xTaskCreate(camera_task, "camera_task", STACK_SIZE_CAMERA, NULL,
                TASK_PRIORITY_CAMERA, &g_device.camera_task_handle);
    xTaskCreate(inference_task, "inference_task", STACK_SIZE_INFERENCE, NULL,
                TASK_PRIORITY_INFERENCE, &g_device.inference_task_handle);
    xTaskCreate(alert_task, "alert_task", STACK_SIZE_ALERT, NULL,
                TASK_PRIORITY_ALERT, &g_device.alert_task_handle);
    xTaskCreate(network_task, "network_task", STACK_SIZE_NETWORK, NULL,
                TASK_PRIORITY_NETWORK, &g_device.network_task_handle);
    xTaskCreate(power_task, "power_task", STACK_SIZE_POWER, NULL,
                TASK_PRIORITY_POWER, &g_device.power_task_handle);
    xTaskCreate(system_status_report_task, "status_task", STACK_SIZE_POWER, NULL,
                2, NULL);

    g_device.state = SYSTEM_STATE_ACTIVE;

    ESP_LOGI("SENTINELEY", "=== All subsystems ONLINE ===");
    ESP_LOGI("SENTINELEY", "Device ID: %08X", g_device.device_id);
    ESP_LOGI("SENTINELEY", "Firmware: %s", g_device.firmware_version);

    /* Signal system ready */
    gpio_set_level(PIN_STATUS_LED, 1);
    alert_system_play_ready_tone();

    /* Delete init task */
    vTaskDelete(g_init_task_handle);
    vTaskDelay(portMAX_DELAY);

error_recovery:
    ESP_LOGE("SENTINELEY", "Entering error recovery");
    vTaskDelay(pdMS_TO_TICKS(5000));
    esp_restart();
}

/*
 * System self-test
 */
static esp_err_t system_self_test(void) {
    ESP_LOGI("SENTINELEY", "Running self-test...");

    /* Check flash size */
    esp_flash_get_chip_info(&(g_device.firmware_version));
    if (g_device.firmware_version < 4 * 1024 * 1024) {
        ESP_LOGE("SENTINELEY", "Flash too small: %d", g_device.firmware_version);
        return ESP_FAIL;
    }

    /* Test I2C */
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (0x15 << 1) | I2C_MASTER_WRITE, true);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(PIN_I2C_PORT, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);

    if (ret == ESP_OK) {
        ESP_LOGW("SENTINELEY", "I2C ACK received (expected for some buses)");
    }

    /* Test I2S */
    i2s_stop(PIN_I2S_PORT);
    ESP_LOGI("SENTINELEY", "I2S self-test passed");

    /* Check heap */
    if (heap_caps_get_free_size(MALLOC_CAP_INTERNAL) < 32000) {
        ESP_LOGE("SENTINELEY", "Insufficient heap");
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI("SENTINELEY", "Heap OK: %d bytes free",
             heap_caps_get_free_size(MALLOC_CAP_INTERNAL));

    return ESP_OK;
}

/*
 * System status report task
 */
static void system_status_report_task(void *pvParameters) {
    (void)pvParameters;

    TickType_t last_wake = xTaskGetTickCount();

    while (1) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(STATUS_REPORT_INTERVAL_MS));

        ESP_LOGI("SENTINELEY", "=== STATUS REPORT ===");
        ESP_LOGI("SENTINELEY", "State: %d | Frames: %u | Inferences: %u | Alerts: %u",
                 g_device.state,
                 g_device.frames_processed,
                 g_device.inference_counter,
                 g_device.alert_counter);
        ESP_LOGI("SENTINELEY", "Drowsy frames: %u | Avg inf time: %.1fus",
                 g_device.drowsy_frames_detected,
                 g_device.avg_inference_time_us);
        power_mgmt_print_status();
        alert_system_print_status();
    }
}
