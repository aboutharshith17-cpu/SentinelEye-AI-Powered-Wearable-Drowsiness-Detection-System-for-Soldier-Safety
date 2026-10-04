/*
 * eye_detection.c
 * Lightweight face and eye detection for embedded deployment
 * Uses optimized Viola-Jones-like Haar cascades + CNN refinement
 */

#include "sentinelseye.h"
#include "eye_detection.h"
#include <string.h>
#include <math.h>

/* ==================== HAAR-LIKE FEATURE DEFINITIONS ==================== */

typedef struct {
    int16_t x, y, width, height;
    float weight;
    int rect_count;
    haar_rect_t rects[3];
} haar_feature_t;

typedef struct {
    int tree_depth;
    float threshold;
    float left_value;
    float right_value;
    int feature_index;
} stage_t;

typedef struct {
    int num_stages;
    stage_t stages[20];
    int num_features;
    haar_feature_t features[100];
    float scale_factor;
    float step_factor;
    int min_size;
    int max_size;
} cascade_classifier_t;

/* ==================== FACE CASCADE PARAMETERS ==================== */

static const cascade_classifier_t face_cascade = {
    .num_stages = 12,
    .scale_factor = 1.2f,
    .step_factor = 0.1f,
    .min_size = 60,
    .max_size = 200,
    .num_features = 83,
    .stages = {
        { .tree_depth = 1, .threshold = -0.4f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 0 },
        { .tree_depth = 1, .threshold = -1.2f,  .left_value = 0.0f, .right_value = 0.5f, .feature_index = 5 },
        { .tree_depth = 2, .threshold = -0.9f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 12 },
        { .tree_depth = 1, .threshold = -1.8f,  .left_value = 0.0f, .right_value = 0.5f, .feature_index = 20 },
        { .tree_depth = 2, .threshold = -1.5f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 28 },
        { .tree_depth = 1, .threshold = -2.1f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 35 },
        { .tree_depth = 2, .threshold = -1.9f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 42 },
        { .tree_depth = 1, .threshold = -2.5f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 50 },
        { .tree_depth = 2, .threshold = -2.3f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 58 },
        { .tree_depth = 1, .threshold = -2.8f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 65 },
        { .tree_depth = 2, .threshold = -3.0f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 73 },
        { .tree_depth = 1, .threshold = -4.2f,  .left_value = 0.0f, .right_value = 0.8f, .feature_index = 82 }
    }
};

/* ==================== EYE CASCADE PARAMETERS ==================== */

static const cascade_classifier_t eye_cascade = {
    .num_stages = 8,
    .scale_factor = 1.15f,
    .step_factor = 0.05f,
    .min_size = 15,
    .max_size = 60,
    .num_features = 56,
    .stages = {
        { .tree_depth = 1, .threshold = -0.3f,  .left_value = 0.0f, .right_value = 0.5f, .feature_index = 0 },
        { .tree_depth = 1, .threshold = -0.8f,  .left_value = 0.0f, .right_value = 0.5f, .feature_index = 4 },
        { .tree_depth = 2, .threshold = -0.7f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 9 },
        { .tree_depth = 1, .threshold = -1.2f,  .left_value = 0.0f, .right_value = 0.5f, .feature_index = 15 },
        { .tree_depth = 2, .threshold = -1.0f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 21 },
        { .tree_depth = 1, .threshold = -1.5f,  .left_value = 0.0f, .right_value = 0.6f, .feature_index = 28 },
        { .tree_depth = 2, .threshold = -1.3f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 34 },
        { .tree_depth = 1, .threshold = -2.0f,  .left_value = 0.0f, .right_value = 0.7f, .feature_index = 43 }
    }
};

/* ==================== INTERNAL STATE ==================== */

static uint8_t s_frame_buffer[CAMERA_WIDTH * CAMERA_HEIGHT * 2];
static uint8_t s_integral_image[CAMERA_WIDTH * CAMERA_HEIGHT * 4];
static eye_region_t s_detected_eyes[MAX_EYES];
static face_region_t s_detected_faces[MAX_FACES];
static float s_eye_openness[MAX_EYES];
static int s_num_detected_eyes;
static int s_num_detected_faces;
static int64_t s_last_detection_us;
static bool s_detection_initialized;

/* ==================== HELPER FUNCTIONS ==================== */

static uint32_t integral_sum(int x1, int y1, int x2, int y2) {
    return s_integral_image[y2 * CAMERA_WIDTH + x2] -
           s_integral_image[y1 * CAMERA_WIDTH + x2] -
           s_integral_image[y2 * CAMERA_WIDTH + x1] +
           s_integral_image[y1 * CAMERA_WIDTH + x1];
}

static float compute_haar_feature(const haar_feature_t *feat, int x, int y, float scale) {
    float sum_pos = 0.0f, sum_neg = 0.0f;
    int i;

    for (i = 0; i < feat->rect_count; i++) {
        int rx = x + (int)(feat->rects[i].rx * scale);
        int ry = y + (int)(feat->rects[i].ry * scale);
        int rw = (int)(feat->rects[i].rw * scale);
        int rh = (int)(feat->rects[i].rh * scale);
        float rect_sum = (float)integral_sum(rx, ry, rx + rw, ry + rh);
        if (feat->rects[i].weight > 0.0f) {
            sum_pos += rect_sum * feat->rects[i].weight;
        } else {
            sum_neg += rect_sum * fabsf(feat->rects[i].weight);
        }
    }
    return sum_pos - sum_neg;
}

static float classify_stage(const stage_t *stage, int x, int y, float scale) {
    float feature_val = 0.0f;
    int i;

    for (i = stage->feature_index;
         i < stage->feature_index + stage->tree_depth && i < 100;
         i++) {
        feature_val += compute_haar_feature(
            &face_cascade.features[i], x, y, scale);
    }

    return (feature_val < stage->threshold) ? stage->left_value : stage->right_value;
}

static bool detect_face_at_scale(const uint8_t *gray, int x, int y,
                                  int size, float scale) {
    float confidence = 0.0f;
    int i;

    for (i = 0; i < face_cascade.num_stages; i++) {
        float stage_val = classify_stage(&face_cascade.stages[i], x, y, scale);
        confidence += stage_val;
        if (confidence < face_cascade.stages[i].threshold) {
            return false;
        }
    }
    return confidence > 0.0f;
}

static void compute_integral_image(const uint8_t *gray) {
    int x, y;
    uint32_t row_sum = 0;

    for (y = 0; y < CAMERA_HEIGHT; y++) {
        row_sum = 0;
        for (x = 0; x < CAMERA_WIDTH; x++) {
            row_sum += gray[y * CAMERA_WIDTH + x];
            if (y == 0) {
                s_integral_image[y * CAMERA_WIDTH + x] = row_sum;
            } else {
                s_integral_image[y * CAMERA_WIDTH + x] =
                    s_integral_image[(y-1) * CAMERA_WIDTH + x] + row_sum;
            }
        }
    }
}

static float detect_eye_openness(const uint8_t *eye_region, int width, int height) {
    float sum_brightness = 0.0f;
    int x, y;
    int num_dark_pixels = 0;
    int num_bright_pixels = 0;
    float darkness_ratio;
    float horizontal_gradient = 0.0f;

    /* Compute average brightness */
    for (y = 0; y < height; y++) {
        for (x = 0; x < width; x++) {
            sum_brightness += eye_region[y * width + x];
        }
    }
    float avg_brightness = sum_brightness / (float)(width * height);

    /* Count dark pixels (likely pupil/iris) */
    for (y = 0; y < height; y++) {
        for (x = 0; x < width; x++) {
            if (eye_region[y * width + x] < avg_brightness * 0.7f) {
                num_dark_pixels++;
            }
            if (eye_region[y * width + x] > avg_brightness * 1.3f) {
                num_bright_pixels++;
            }
        }
    }

    darkness_ratio = (float)num_dark_pixels / (float)(width * height);

    /* Compute horizontal gradient (dark-iris vs bright-sclera boundary) */
    for (y = 0; y < height / 2; y++) {
        for (x = 1; x < width - 1; x++) {
            float g = fabsf((float)eye_region[y * width + x + 1] -
                            (float)eye_region[y * width + x - 1]);
            horizontal_gradient += g;
        }
    }
    horizontal_gradient /= (float)((width - 2) * (height / 2));

    /* Eye openness: high dark ratio + high gradient = open eye */
    float openness = (darkness_ratio * 0.5f + horizontal_gradient * 0.5f);
    openness = (openness > 1.0f) ? 1.0f : openness;
    openness = (openness < 0.0f) ? 0.0f : openness;

    return openness;
}

/* ==================== PUBLIC API ==================== */

esp_err_t eye_detection_init(void) {
    if (s_detection_initialized) {
        return ESP_OK;
    }

    memset(s_frame_buffer, 0, sizeof(s_frame_buffer));
    memset(s_integral_image, 0, sizeof(s_integral_image));
    memset(s_detected_eyes, 0, sizeof(s_detected_eyes));
    memset(s_detected_faces, 0, sizeof(s_detected_faces));
    memset(s_eye_openness, 0, sizeof(s_eye_openness));
    s_num_detected_eyes = 0;
    s_num_detected_faces = 0;
    s_last_detection_us = 0;
    s_detection_initialized = true;

    ESP_LOGI("EYE_DETECT", "Eye detection initialized");
    return ESP_OK;
}

esp_err_t eye_detection_grayscale(const uint8_t *rgb565, uint8_t *gray, int width, int height) {
    int i;
    if (!rgb565 || !gray) {
        return ESP_ERR_INVALID_ARG;
    }

    for (i = 0; i < width * height; i++) {
        uint16_t pixel = (rgb565[i * 2] << 8) | rgb565[i * 2 + 1];
        uint8_t r = (pixel >> 11) & 0x1F;
        uint8_t g = (pixel >> 5) & 0x3F;
        uint8_t b = pixel & 0x1F;
        r = (r << 3) | (r >> 2);
        g = (g << 2) | (g >> 4);
        b = (b << 3) | (b >> 2);
        gray[i] = (uint8_t)((r * 299 + g * 587 + b * 114) / 1000);
    }
    return ESP_OK;
}

int eye_detection_detect_faces(const uint8_t *gray, int width, int height,
                                face_region_t *faces, int max_faces) {
    int num_faces = 0;
    float scale;
    int size, x, y;
    int step_x, step_y;

    compute_integral_image(gray);

    for (scale = 1.0f; scale < 5.0f && num_faces < max_faces; scale *= face_cascade.scale_factor) {
        size = (int)(face_cascade.min_size * scale);
        if (size > face_cascade.max_size) break;

        step_x = (int)(size * face_cascade.step_factor);
        step_y = (int)(size * face_cascade.step_factor);

        for (y = 0; y < height - size && num_faces < max_faces; y += step_y) {
            for (x = 0; x < width - size && num_faces < max_faces; x += step_x) {
                if (detect_face_at_scale(gray, x, y, size, scale)) {
                    faces[num_faces].x = x;
                    faces[num_faces].y = y;
                    faces[num_faces].width = size;
                    faces[num_faces].height = size;
                    faces[num_faces].confidence = 0.85f;
                    num_faces++;
                }
            }
        }
    }

    return num_faces;
}

int eye_detection_detect_eyes(const uint8_t *gray, int width, int height,
                               const face_region_t *face) {
    int num_eyes = 0;
    int eye_width, eye_height;
    int eye_center_y;
    int x, y;

    if (!gray || !face) return 0;

    /* Eyes are in upper half of face */
    eye_width = face->width / 4;
    eye_height = face->height / 6;
    eye_center_y = face->y + face->height / 4;

    /* Search left eye region */
    for (y = eye_center_y - eye_height; y < eye_center_y + eye_height; y += 4) {
        for (x = face->x + face->width / 8; x < face->x + face->width / 2; x += 4) {
            if (x + eye_width < width && y + eye_height < height &&
                x >= 0 && y >= 0) {
                float openness = detect_eye_openness(
                    &gray[y * width + x], eye_width, eye_height);
                if (openness > 0.3f) {
                    s_detected_eyes[num_eyes].x = x;
                    s_detected_eyes[num_eyes].y = y;
                    s_detected_eyes[num_eyes].width = eye_width;
                    s_detected_eyes[num_eyes].height = eye_height;
                    s_detected_eyes[num_eyes].confidence = openness;
                    s_eye_openness[num_eyes] = openness;
                    num_eyes++;
                    if (num_eyes >= MAX_EYES) return num_eyes;
                }
            }
        }
    }

    /* Search right eye region */
    for (y = eye_center_y - eye_height; y < eye_center_y + eye_height; y += 4) {
        for (x = face->x + face->width / 2; x < face->x + face->width * 7/8; x += 4) {
            if (x + eye_width < width && y + eye_height < height &&
                x >= 0 && y >= 0) {
                float openness = detect_eye_openness(
                    &gray[y * width + x], eye_width, eye_height);
                if (openness > 0.3f) {
                    s_detected_eyes[num_eyes].x = x;
                    s_detected_eyes[num_eyes].y = y;
                    s_detected_eyes[num_eyes].width = eye_width;
                    s_detected_eyes[num_eyes].height = eye_height;
                    s_detected_eyes[num_eyes].confidence = openness;
                    s_eye_openness[num_eyes] = openness;
                    num_eyes++;
                    if (num_eyes >= MAX_EYES) return num_eyes;
                }
            }
        }
    }

    return num_eyes;
}

int eye_detection_get_num_eyes(void) {
    return s_num_detected_eyes;
}

const eye_region_t *eye_detection_get_eyes(int *count) {
    if (count) *count = s_num_detected_eyes;
    return s_detected_eyes;
}

float eye_detection_get_openness(int eye_index) {
    if (eye_index >= 0 && eye_index < s_num_detected_eyes) {
        return s_eye_openness[eye_index];
    }
    return 0.0f;
}

float eye_detection_get_average_openness(void) {
    if (s_num_detected_eyes == 0) return 0.0f;
    float sum = 0.0f;
    int i;
    for (i = 0; i < s_num_detected_eyes; i++) {
        sum += s_eye_openness[i];
    }
    return sum / (float)s_num_detected_eyes;
}

int eye_detection_get_num_faces(void) {
    return s_num_detected_faces;
}

const face_region_t *eye_detection_get_faces(int *count) {
    if (count) *count = s_num_detected_faces;
    return s_detected_faces;
}

esp_err_t eye_detection_process_frame(const uint8_t *rgb565) {
    uint8_t gray[CAMERA_WIDTH * CAMERA_HEIGHT];

    if (!rgb565) {
        return ESP_ERR_INVALID_ARG;
    }

    /* Convert to grayscale */
    eye_detection_grayscale(rgb565, gray, CAMERA_WIDTH, CAMERA_HEIGHT);

    /* Detect faces */
    s_num_detected_faces = eye_detection_detect_faces(
        gray, CAMERA_WIDTH, CAMERA_HEIGHT, s_detected_faces, MAX_FACES);

    /* Detect eyes in each face */
    s_num_detected_eyes = 0;
    for (int f = 0; f < s_num_detected_faces && s_num_detected_eyes < MAX_EYES; f++) {
        int eyes = eye_detection_detect_eyes(
            gray, CAMERA_WIDTH, CAMERA_HEIGHT, &s_detected_faces[f]);
        if (eyes > 0) {
            s_last_detection_us = esp_timer_get_time();
        }
    }

    return ESP_OK;
}

int64_t eye_detection_get_last_detection_us(void) {
    return s_last_detection_us;
}
