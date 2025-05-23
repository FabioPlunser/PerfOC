#include "benchmark.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef struct
{
  int *data;
  size_t size;
  size_t capacity;
} Array;

int array_get(void *ds, size_t index)
{
  Array *arr = (Array *)ds;
  return arr->data[index];
}

void array_set(void *ds, size_t index, int value)
{
  Array *arr = (Array *)ds;
  arr->data[index] = value;
}

void array_insert(void *ds, size_t index, int value)
{
  Array *arr = (Array *)ds;

  if (arr->size < arr->capacity)
  {
    // Shift elements to the right to make space
    memmove(&arr->data[index + 1], &arr->data[index],
            (arr->size - index) * sizeof(int));
    arr->data[index] = value;
    arr->size++;
  }
}

void array_delete(void *ds, size_t index)
{
  Array *arr = (Array *)ds;
  if (arr->size > 1)
  {
    // Shift elements to the left to fill the gap
    memmove(&arr->data[index], &arr->data[index + 1],
            (arr->size - index - 1) * sizeof(int));
    arr->size--;
  }
}

void array_destroy(void *ds)
{
  Array *arr = (Array *)ds;
  free(arr->data);
  free(arr);
}

// Factory function to create array data structure
DataStructure create_array(size_t initial_size)
{
  Array *arr = malloc(sizeof(Array));
  arr->capacity = initial_size + 100; // Extra space for insertions
  arr->data = malloc(arr->capacity * sizeof(int));
  arr->size = initial_size;

  // Pre-initialize with data (0, 1, 2, 3, ...)
  for (size_t i = 0; i < initial_size; i++)
  {
    arr->data[i] = (int)i;
  }

  DataStructure ds = {
      .data_structure = arr,
      .get = array_get,
      .set = array_set,
      .insert = array_insert,
      .delete = array_delete,
      .destroy = array_destroy,
      .current_size = &arr->size};

  return ds;
}
