/*
 * camera_task.c
 * Camera frame capture task for ESP32-S3
 * Handles OV5647 initialization, frame capture, and buffer management
 */

#include "sentinelseye.h"
#include "eye_detection.h"
#include "tflite_inference.h"
#include "alert_system.h"
#include <string.h>

/* Camera frame buffer */
static uint8_t s_frame_buffer[CAMERA_FRAME_BUFFER_SIZE];
static QueueHandle_t s_frame_queue = NULL;
static TaskHandle_t s_camera_task_handle = NULL;

/* Camera configuration */
static camera_config_t s_camera_config = {
    .pin_pwdn = PIN_CAMERA_PWDN,
    .pin_reset = PIN_CAMERA_RESET,
    .pin_xclk = PIN_CAMERA_XCLK,
    .pin_sscb_sda = PIN_CAMERA_SIOD,
    .pin_sscb_scl = PIN_CAMERA_SIOC,
    .pin_d7 = PIN_CAMERA_D7,
    .pin_d6 = PIN_CAMERA_D6,
    .pin_d5 = PIN_CAMERA_D5,
    .pin_d4 = PIN_CAMERA_D4,
    .pin_d3 = PIN_CAMERA_D3,
    .pin_d2 = PIN_CAMERA_D2,
    .pin_d1 = PIN_CAMERA_D1,
    .pin_d0 = PIN_CAMERA_D0,
    .pin_vsync = PIN_CAMERA_VSYNC,
    .pin_href = PIN_CAMERA_HREF,
    .pin_pclk = PIN_CAMERA_PCLK,
    .xclk_freq_hz = CAMERA_XCLK_FREQ,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = CAMERA_FORMAT,
    .frame_size = FRAMESIZE_240X240,
    .jpeg_quality = CAMERA_QUALITY,
    .fb_count = 2,
    .grab_mode = CAMERA_GRAB_LATEST
};

/*
 * Camera capture callback - called from ISR context
 */
static bool IRAM_ATTR camera_capture_callback(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    esp_err_t ret;

    /* Get current frame buffer */
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        return false;
    }

    /* Validate frame */
    if (fb->len != CAMERA_FRAME_BUFFER_SIZE) {
        esp_camera_fb_return(fb);
        return false;
    }

    /* Copy to our frame buffer (non-blocking) */
    memcpy(s_frame_buffer, fb->buf, fb->len);

    /* Return frame buffer to driver */
    esp_camera_fb_return(fb);

    /* Notify inference task */
    if (s_frame_queue) {
        ret = xQueueSendFromISR(s_frame_queue, s_frame_buffer,
                                &xHigherPriorityTaskWoken);
        if (ret == pdTRUE) {
            g_device.frames_processed++;
        }
    }

    /* Context switch if needed */
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);

    return true;
}

/*
 * Initialize camera
 */
esp_err_t sentinelseye_camera_init(void) {
    esp_err_t ret;

    ESP_LOGI("CAMERA", "Initializing OV5647 camera...");

    /* Power down sequence */
    gpio_set_level(PIN_CAMERA_PWDN, 1);
    gpio_set_level(PIN_CAMERA_RESET, 0);
    vTaskDelay(pdMS_TO_TICKS(10));

    /* Power up sequence */
    gpio_set_level(PIN_CAMERA_PWDN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(PIN_CAMERA_RESET, 1);
    vTaskDelay(pdMS_TO_TICKS(20));

    /* Initialize camera driver */
    ret = esp_camera_init(&s_camera_config);
    if (ret != ESP_OK) {
        ESP_LOGE("CAMERA", "Camera init FAILED: %s", esp_err_to_name(ret));
        return ret;
    }

    /* Get camera sensor */
    sensor_t *sensor = esp_camera_sensor_get();
    if (!sensor) {
        ESP_LOGE("CAMERA", "Failed to get camera sensor");
        return ESP_FAIL;
    }

    /* Configure sensor */
    sensor->set_brightness(sensor, 0);      /* -2 to 2 */
    sensor->set_contrast(sensor, 0);        /* -2 to 2 */
    sensor->set_saturation(sensor, 0);      /* -2 to 2 */
    sensor->set_whitebal(sensor, 1);        /* 0 = disable, 1 = enable */
    sensor->set_awb_gain(sensor, 1);        /* Auto white balance gain */
    sensor->set_wb_mode(sensor, 0);         /* 0 = auto */
    sensor->set_exposure_ctrl(sensor, 1);   /* Auto exposure */
    sensor->set_aec2(sensor, 0);            /* AEC sensor */
    sensor->set_gain_ctrl(sensor, 1);       /* Auto gain */
    sensor->set_agc_gain(sensor, 0);        /* 0 to 30 */
    sensor->set_gainceiling(sensor, (gainceiling_t)0); /* 0 to 6 */
    sensor->set_bpc(sensor, 0);             /* Black pixel correction */
    sensor->set_wpc(sensor, 1);             /* White pixel correction */
    sensor->set_raw_gma(sensor, 1);         /* RAW gamma */
    sensor->set_lenc(sensor, 1);            /* Lens correction */
    sensor->set_hmirror(sensor, 0);         /* Horizontal mirror */
    sensor->set_vflip(sensor, 0);           /* Vertical flip */
    sensor->set_colorbar(sensor, 0);        /* Test pattern */

    ESP_LOGI("CAMERA", "Camera configured: %dx%d @ %dfps",
             CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS);

    /* Create frame queue */
    s_frame_queue = xQueueCreate(INFERENCE_QUEUE_LEN, CAMERA_FRAME_BUFFER_SIZE);
    if (!s_frame_queue) {
        ESP_LOGE("CAMERA", "Frame queue creation FAILED");
        esp_camera_deinit();
        return ESP_ERR_NO_MEM;
    }

    /* Capture initial frame (discard first few for auto-exposure) */
    for (int i = 0; i < 3; i++) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb) {
            esp_camera_fb_return(fb);
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    ESP_LOGI("CAMERA", "Camera initialization COMPLETE");
    return ESP_OK;
}

/*
 * Camera capture task
 */
void camera_task(void *pvParameters) {
    (void)pvParameters;
    esp_err_t ret;
    uint32_t capture_count = 0;
    uint64_t last_capture_us = 0;
    uint64_t capture_interval_us = 1000000 / CAMERA_FPS; /* ~66ms */

    ESP_LOGI("CAMERA", "Camera task started");

    while (1) {
        uint64_t now = esp_timer_get_time();

        /* Throttle capture rate */
        if (now - last_capture_us < capture_interval_us) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        /* Capture frame */
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE("CAMERA", "Failed to capture frame");
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        /* Validate frame */
        if (fb->width != CAMERA_WIDTH || fb->height != CAMERA_HEIGHT) {
            ESP_LOGW("CAMERA", "Unexpected frame size: %dx%d",
                     fb->width, fb->height);
            esp_camera_fb_return(fb);
            continue;
        }

        /* Copy frame data */
        if (fb->len <= CAMERA_FRAME_BUFFER_SIZE) {
            memcpy(s_frame_buffer, fb->buf, fb->len);
            capture_count++;
            last_capture_us = now;

            /* Send to inference queue */
            if (s_frame_queue) {
                if (xQueueSend(s_frame_queue, s_frame_buffer, pdMS_TO_TICKS(10)) != pdTRUE) {
                    ESP_LOGW("CAMERA", "Frame queue FULL - dropping frame");
                }
            }

            g_device.frames_processed++;
            power_mgmt_set_activity();
        }

        /* Return frame buffer */
        esp_camera_fb_return(fb);

        /* Yield to other tasks */
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

/*
 * Get current frame buffer
 */
const uint8_t *camera_task_get_frame_buffer(void) {
    return s_frame_buffer;
}

/*
 * Get frame queue handle
 */
QueueHandle_t camera_task_get_queue(void) {
    return s_frame_queue;
}
