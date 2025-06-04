
#ifndef TIERED_ARRAY_H
#define TIERED_ARRAY_H
#include <stddef.h>
#include "benchmark.h"

typedef struct TieredChunk
{
  int *elements;
  size_t count;
  size_t capacity;
} TieredChunk;

typedef struct
{
  TieredChunk **chunks;
  size_t chunk_count;
  size_t chunk_capacity;
  size_t total_elements;
  size_t chunk_size;
} TieredArray;

// Different configurations
Container create_tiered_array_8();
Container create_tiered_array_16();
Container create_tiered_array_32();
Container create_tiered_array_64();
Container create_tiered_array_128();
Container create_tiered_array_256();

#endif
