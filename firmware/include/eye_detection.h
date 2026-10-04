#ifndef EYE_DETECTION_H
#define EYE_DETECTION_H

#include "sentinelseye.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Detection Limits */
#define MAX_FACES     5
#define MAX_EYES      10

/* Eye Region Structure */
typedef struct {
    int x, y;
    int width, height;
    float confidence;
} eye_region_t;

/* Face Region Structure */
typedef struct {
    int x, y;
    int width, height;
    float confidence;
} face_region_t;

/* Initialization */
esp_err_t eye_detection_init(void);

/* Frame Processing */
esp_err_t eye_detection_process_frame(const uint8_t *rgb565);
esp_err_t eye_detection_grayscale(const uint8_t *rgb565, uint8_t *gray,
                                   int width, int height);

/* Detection Results */
int eye_detection_detect_faces(const uint8_t *gray, int width, int height,
                                face_region_t *faces, int max_faces);
int eye_detection_detect_eyes(const uint8_t *gray, int width, int height,
                               const face_region_t *face);
int eye_detection_get_num_eyes(void);
const eye_region_t *eye_detection_get_eyes(int *count);
int eye_detection_get_num_faces(void);
const face_region_t *eye_detection_get_faces(int *count);
float eye_detection_get_openness(int eye_index);
float eye_detection_get_average_openness(void);
int64_t eye_detection_get_last_detection_us(void);

#ifdef __cplusplus
}
#endif

#endif /* EYE_DETECTION_H */
