#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tiered_array.h"

TieredChunk *create_chunk(size_t capacity)
{
  TieredChunk *chunk = malloc(sizeof(TieredChunk));
  if (!chunk)
  {
    fprintf(stderr, "Error: Failed to allocate memory for chunk\n");
    exit(1);
  }

  chunk->elements = malloc(capacity * sizeof(int));
  if (!chunk->elements)
  {
    free(chunk);
    fprintf(stderr, "Error: Failed to allocate memory for chunk elements\n");
    exit(1);
  }

  chunk->count = 0;
  chunk->capacity = capacity;

  return chunk;
}

void free_chunk(TieredChunk *chunk)
{
  if (chunk)
  {
    free(chunk->elements);
    free(chunk);
  }
}

int find_chunk_and_index(
    TieredArray *array,
    size_t global_index,
    size_t *chunk_index,
    size_t *local_idx)
{
  if (global_index >= array->total_elements)
  {
    fprintf(stderr, "Error: Index out of bounds\n");
    return -1;
  }

  size_t cumulative = 0;

  for (size_t i = 0; i < array->chunk_count; i++)
  {
    if (cumulative + array->chunks[i]->count > global_index)
    {
      *chunk_index = i;
      *local_idx = global_index - cumulative;
      return 0;
    }
    cumulative += array->chunks[i]->count;
  }

  fprintf(stderr, "Error: Index out of bounds\n");
  return -1;
}

int expand_chunk_array(TieredArray *array)
{
  if (array->chunk_count >= array->chunk_capacity)
  {
    size_t new_capacity = array->chunk_capacity * 2;
    TieredChunk **new_chunks = realloc(array->chunks, new_capacity * sizeof(TieredChunk *));
    if (!new_chunks)
    {
      fprintf(stderr, "Error: Failed to allocate memory for new chunk array\n");
      exit(1);
    }

    array->chunks = new_chunks;
    array->chunk_capacity = new_capacity;
  }
  return 0;
}

void tiered_init(void *data, size_t size, size_t element_size)
{
  TieredArray *array = (TieredArray *)data;
  array->chunk_count = 0;
  array->chunk_capacity = 0;
  array->total_elements = 0;

  size_t initial_chunks = (size + array->chunk_size - 1) / array->chunk_size;
  array->chunk_capacity = initial_chunks > 4 ? initial_chunks : 4;

  array->chunks = malloc(array->chunk_capacity * sizeof(TieredChunk *));
  if (!array->chunks)
  {
    fprintf(stderr, "Error: Failed to allocate chunk array\n");
    exit(1);
  }

  // Create chunks and fill with initial data
  size_t remaining = size;
  size_t value_counter = 0;

  while (remaining > 0)
  {
    size_t chunk_elements = (remaining > array->chunk_size) ? array->chunk_size : remaining;

    TieredChunk *chunk = create_chunk(array->chunk_size);
    if (!chunk)
    {
      fprintf(stderr, "Error: Failed to create chunk\n");
      exit(1);
    }

    // Fill chunk with initial values
    for (size_t i = 0; i < chunk_elements; i++)
    {
      chunk->elements[i] = value_counter % 1000;
      value_counter++;
    }
    chunk->count = chunk_elements;

    array->chunks[array->chunk_count++] = chunk;
    array->total_elements += chunk_elements;
    remaining -= chunk_elements;
  }
}

int tiered_read(void *data, size_t index)
{
  TieredArray *array = (TieredArray *)data;
  size_t chunk_idx, local_idx;

  if (find_chunk_and_index(array, index, &chunk_idx, &local_idx) != 0)
  {
    fprintf(stderr, "Error: Tiered array read index out of bounds\n");
    return -1;
  }

  return array->chunks[chunk_idx]->elements[local_idx];
}

void tiered_write(void *data, size_t index, int value)
{
  TieredArray *array = (TieredArray *)data;
  size_t chunk_idx, local_idx;

  if (find_chunk_and_index(array, index, &chunk_idx, &local_idx) != 0)
  {
    fprintf(stderr, "Error: Tiered array write index out of bounds\n");
    return;
  }

  array->chunks[chunk_idx]->elements[local_idx] = value;
}

int tiered_insert(void *data, size_t index, int value)
{
  TieredArray *array = (TieredArray *)data;

  // Handle insertion at the end
  if (index >= array->total_elements)
  {
    // Find last chunk or create new one
    TieredChunk *last_chunk = array->chunks[array->chunk_count - 1];
    if (!last_chunk || last_chunk->count >= last_chunk->capacity)
    {
      if (expand_chunk_array(array) != 0)
      {
        fprintf(stderr, "Error: Failed to expand chunk array\n");
        return -1;
      }

      TieredChunk *new_chunk = create_chunk(array->chunk_size);
      if (!new_chunk)
      {
        fprintf(stderr, "Error: Failed to create new chunk\n");
        return -1;
      }

      array->chunks[array->chunk_count++] = new_chunk;
      last_chunk = new_chunk;
    }

    last_chunk->elements[last_chunk->count++] = value;
    array->total_elements++;
    return 0;
  }

  // Handle insertion in the middle
  size_t chunk_idx, local_idx;
  if (find_chunk_and_index(array, index, &chunk_idx, &local_idx) != 0)
  {
    fprintf(stderr, "Error: Tiered array insert index out of bounds\n");
    return -1;
  }

  TieredChunk *target_chunk = array->chunks[chunk_idx];

  // If chunk has space, insert directly
  if (target_chunk->count < target_chunk->capacity)
  {
    memmove(
        &target_chunk->elements[local_idx + 1],
        &target_chunk->elements[local_idx],
        (target_chunk->count - local_idx) * sizeof(int));

    target_chunk->elements[local_idx] = value;
    target_chunk->count++;
    array->total_elements++;
    return 0;
  }

  // Chunk is full, need to shift elements or create new chunk
  // For simplicity, we'll shift elements to the right through chunks
  int overflow = target_chunk->elements[target_chunk->capacity - 1];

  memmove(
      &target_chunk->elements[local_idx + 1],
      &target_chunk->elements[local_idx],
      (target_chunk->count - local_idx) * sizeof(int));

  target_chunk->elements[local_idx] = value;

  for (size_t i = chunk_idx; i < array->chunk_count; i++)
  {
    TieredChunk *chunk = array->chunks[i];
    if (chunk->count < chunk->capacity)
    {
      memmove(
        &chunk->elements[0],
        &chunk->elements[1],
          chunk->count * sizeof(int));
      chunk->elements[chunk->count - 1] = overflow;
      chunk->count++;
      array->total_elements++;
      return 0;
    }
    // This chunk is also full, continue propagation
    int next_overflow = chunk->elements[chunk->capacity - 1];
    memmove(
      &chunk->elements[0],
      &chunk->elements[1],
        chunk->count * sizeof(int));
    chunk->elements[0] = overflow;
    overflow = next_overflow;
  }

  // All chunks are full, need a new chunk for overflow
  if (expand_chunk_array(array) != 0)
  {
    fprintf(stderr, "Error: Failed to expand chunk array\n");
    return -1;
  }

  TieredChunk *new_chunk = create_chunk(array->chunk_size);
  if (!new_chunk)
  {
    fprintf(stderr, "Error: Failed to create new chunk\n");
    return -1;
  }

  new_chunk->elements[0] = overflow;
  new_chunk->count = 1;
  array->chunks[array->chunk_count++] = new_chunk;
  array->total_elements++;
  return 0;
}

int tiered_delete(void *data, size_t index)
{
  TieredArray *array = (TieredArray *)data;
  size_t chunk_idx, local_idx;
  if (find_chunk_and_index(array, index, &chunk_idx, &local_idx) != 0)
  {
    fprintf(stderr, "Error: Tiered array delete index out of bounds\n");
    return -1;
  }

  TieredChunk *target_chunk = array->chunks[chunk_idx];

  // Remove element from chunk
  memmove(
      &target_chunk->elements[local_idx],
      &target_chunk->elements[local_idx + 1],
      (target_chunk->count - local_idx - 1) * sizeof(int));
  target_chunk->count--;
  array->total_elements--;

  for (size_t i = chunk_idx; i < array->chunk_count - 1; i++)
  {
    TieredChunk *current = array->chunks[i];
    TieredChunk *next = array->chunks[i + 1];

    if (next->count > 0)
    {
      current->elements[current->count++] = next->elements[0];
      memmove(
          &next->elements[0],
          &next->elements[1],
          (next->count - 1) * sizeof(int));
      next->count--;
    }
  }

  // Remove empty chunks from the end
  while (array->chunk_count > 0 && array->chunks[array->chunk_count - 1]->count == 0)
  {
    free_chunk(array->chunks[array->chunk_count - 1]);
    array->chunk_count--;
  }
  return 0;
}

void tiered_cleanup(void *data)
{
  TieredArray *array = (TieredArray *)data;
  for (size_t i = 0; i < array->chunk_count; i++)
  {
    free_chunk(array->chunks[i]);
  }
  free(array->chunks);
  array->chunks = NULL;
  array->chunk_count = 0;
  array->chunk_capacity = 0;
  array->total_elements = 0;
}

Container create_tiered_array_with_size(size_t chunk_size)
{
  Container container = {0};

  TieredArray *array = malloc(sizeof(TieredArray));
  if (!array)
  {
    fprintf(stderr, "Error: Failed to allocate memory for tiered array\n");
    exit(1);
  }

  array->chunks = NULL;
  array->chunk_count = 0;
  array->chunk_capacity = 0;
  array->total_elements = 0;
  array->chunk_size = chunk_size;

  container.data = array;
  container.element_size = sizeof(int);
  container.read = tiered_read;
  container.write = tiered_write;
  container.insert = tiered_insert;
  container.delete = tiered_delete;
  container.init = tiered_init;
  container.cleanup = tiered_cleanup;

  return container;
}

Container create_tiered_array_8()
{
  return create_tiered_array_with_size(8);
}

Container create_tiered_array_16()
{
  return create_tiered_array_with_size(16);
}

Container create_tiered_array_32()
{
  return create_tiered_array_with_size(32);
}

Container create_tiered_array_64()
{
  return create_tiered_array_with_size(64);
}

Container create_tiered_array_128()
{
  return create_tiered_array_with_size(128);
}

Container create_tiered_array_256()
{
  return create_tiered_array_with_size(256);
}