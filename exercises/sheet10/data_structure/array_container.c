#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "benchmark.h"
#include <stdint.h>

typedef struct
{
    void *elements;
    size_t size;
    size_t capacity;
    size_t element_size;
    size_t current_pos;
} ArrayData;

static int array_read(void *data, size_t index)
{
    ArrayData *array = (ArrayData *)data;
    if (index >= array->size)
    {
        fprintf(stderr, "Error: Array read index out of bounds\n");
        return -1;
    }
    int value;
    memcpy(&value, (char *)array->elements + (index * array->element_size), sizeof(int));
    return value;
}

static void array_write(void *data, size_t index, int value)
{
    ArrayData *array = (ArrayData *)data;
    if (index >= array->size)
    {
        fprintf(stderr, "Error: Array write index out of bounds\n");
        return;
    }
    memcpy((char *)array->elements + (index * array->element_size), &value, sizeof(int));
}

static int array_insert(void *data, size_t index, int value)
{
    ArrayData *array = (ArrayData *)data;

    if (index > array->size)
    {
        fprintf(stderr, "Error: Array insert index out of bounds\n");
        return -1;
    }
    if (array->size >= array->capacity)
    {
        fprintf(stderr, "Error: Array insert capacity exceeded\n");
        return -1;
    }

    if (index < array->size)
    {
        memmove(
            (char *)array->elements + ((index + 1) * array->element_size),
            (char *)array->elements + (index * array->element_size),
            (array->size - index) * array->element_size);
    }

    memcpy((char *)array->elements + (index * array->element_size), &value, sizeof(int));
    array->size++;
    return 0;
}

static int array_delete(void *data, size_t index)
{
    ArrayData *array = (ArrayData *)data;

    if (index >= array->size)
    {
        fprintf(stderr, "Error: Array delete index out of bounds\n");
        return -1;
    }

    if (index < array->size - 1)
    {
        memmove(
            (char *)array->elements + (index * array->element_size),
            (char *)array->elements + ((index + 1) * array->element_size),
            (array->size - index - 1) * array->element_size);
    }

    array->size--;
    return 0;
}

static void array_init(void *data, size_t size, size_t element_size)
{
    ArrayData *array = (ArrayData *)data;

    if (element_size > 0 && size > SIZE_MAX / element_size)
    {
        fprintf(stderr, "Error: Allocation size would overflow (elements: %zu, size: %zu)\n",
                size, element_size);
        exit(1);
    }

    array->capacity = size + 1;
    array->size = size;
    array->element_size = element_size;

    array->elements = malloc(array->capacity * array->element_size);
    if (!array->elements)
    {
        fprintf(stderr, "Error: Failed to allocate %zu bytes for array\n",
                array->capacity * array->element_size);
        exit(1);
    }

    for (size_t i = 0; i < size; i++)
    {
        int val = i % 1000;
        memcpy((char *)array->elements + (i * array->element_size), &val, sizeof(int));
    }
}

static void array_cleanup(void *data)
{
    ArrayData *array = (ArrayData *)data;
    printf("Cleaning up array container\n");
    printf("Array size: %zu\n", array->size);
    printf("Array capacity: %zu\n", array->capacity);
    printf("Array current position: %zu\n", array->current_pos);
    // printf("Array elements: ");
    // for (size_t i = 0; i < array->size; i++)
    //{
    //     printf("%d ", *((int *)((char *)array->elements + (i * array->element_size))));
    // }
    // printf("\n");
    //
    if (array->elements != NULL)
    {
        free(array->elements);
        array->elements = NULL;
    }

    array->size = 0;
    array->capacity = 0;
    array->current_pos = 0;
}

Container create_array_container()
{
    Container container;
    ArrayData *array_data = (ArrayData *)malloc(sizeof(ArrayData));
    if (!array_data)
    {
        fprintf(stderr, "Error: Failed to allocate memory for array container\n");
        exit(1);
    }

    array_data->elements = NULL;
    array_data->capacity = 0;
    array_data->size = 0;
    array_data->element_size = sizeof(int);
    array_data->current_pos = 0;

    container.data = array_data;
    container.element_size = sizeof(int);
    container.read = array_read;
    container.write = array_write;
    container.insert = array_insert;
    container.delete = array_delete;
    container.init = array_init;
    container.cleanup = array_cleanup;

    return container;
}