#ifndef TFLITE_INFERENCE_H
#define TFLITE_INFERENCE_H

#include "sentinelseye.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Inference Configuration */
#define NN_CONFIDENCE_THRESHOLD 0.75
#define NN_INPUT_WIDTH          24
#define NN_INPUT_HEIGHT         24
#define NN_INPUT_CHANNELS       3
#define NN_NUM_CLASSES          3
#define NN_TENSOR_ARENA_SIZE    20000

/* Inference Initialization */
esp_err_t tflite_inference_init(void);
esp_err_t tflite_inference_reset_stats(void);

/* Frame Preprocessing */
esp_err_t tflite_inference_preprocess(const uint8_t *rgb_frame, int width, int height,
                                       float *nn_input);

/* Inference Execution */
inference_result_t tflite_inference_run(float *nn_input);
float tflite_inference_get_confidence(void);
int64_t tflite_inference_get_last_time_us(void);
uint32_t tflite_inference_get_count(void);

/* Model Info */
const char *tflite_inference_get_model_version(void);
int tflite_inference_get_param_count(void);

#ifdef __cplusplus
}
#endif

#endif /* TFLITE_INFERENCE_H */
