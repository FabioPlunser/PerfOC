#ifndef BENCHMARK_H
#define BENCHMARK_H
#include <stdlib.h>

typedef struct
{
    void *data;
    size_t element_size;
    int (*read)(void *data, size_t index);
    void (*write)(void *data, size_t index, int value);
    int (*insert)(void *data, size_t index, int value);
    int (*delete)(void *data, size_t index);
    void (*init)(void *data, size_t size, size_t element_size);
    void (*cleanup)(void *data);
} Container;

typedef struct
{
    Container container;
    unsigned char *operation_sequence;
    size_t sequence_length;
    size_t container_size;
    double ratio;
} Benchmark;

#endif // BENCHMARK_H