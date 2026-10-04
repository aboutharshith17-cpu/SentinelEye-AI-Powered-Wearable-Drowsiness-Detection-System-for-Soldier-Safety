cmake_minimum_required(VERSION 3.16)
set(SENTINELEY_VERSION "1.0.0")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(sentinelseye VERSION ${SENTINELEY_VERSION})

idf_component_register(
    SRCS
        "src/main.c"
        "src/eye_detection.c"
        "src/tflite_inference.c"
        "src/alert_system.c"
        "src/power_mgmt.c"
    INCLUDE_DIRS
        "include"
    REQUIRES
        driver
        esp_camera
        esp_timer
        esp_system
        esp_wifi
        esp_bt
        nvs_flash
        bt
        esp_hidd
        esp_https_ota
        freertos
        json
        spiffs
        fatfs
        wear_levelling
)

# TFLite Micro
idf_build_get_property(idf_path IDF_PATH)
set(TFLM_PATH "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro")

target_include_directories(${COMPONENT_LIB}
    PUBLIC
        "${TFLM_PATH}"
        "${CMAKE_SOURCE_DIR}/third_party"
)

target_sources(${COMPONENT_LIB}
    PRIVATE
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/debug_log.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/memory_arena_threshold_test.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_error_reporter.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_interpreter.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_mutable_op_resolver.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_optional_debug_tools.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_profiler.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_resource_variable.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_string.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_time.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/micro_utils.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/async/async_subgraph.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/async/async_subgraph_plugin.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/error_reporter.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/flatbuffer_conversions.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/interpreter.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/operator.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/op_resolver.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/tensor.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/tensor_arena.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/core/api/tensor_utils.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/kernels/kernel_util.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/conv.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/depthwise_conv.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/fully_connected.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/mean.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/pooling.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/reshape.cc"
        "${CMAKE_SOURCE_DIR}/third_party/tensorflow/lite/micro/kernels/softmax.cc"
)

# Build optimizations
target_compile_definitions(${COMPONENT_LIB} PUBLIC
    TF_LITE_STATIC_MEMORY=1
    TF_LITE_DISABLE_X86_NEON=1
    TFLITE_MICRO_TENSOR_ARENA_SIZE=100000
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -Os
    -ffunction-sections
    -fdata-sections
)
