#ifndef BENCHMARK_H
#define BENCHMARK_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>  // Add this for bool type

typedef enum
{
  OP_READ,
  OP_WRITE,
  OP_INSERT,
  OP_DELETE
} OperationType;

typedef struct
{
  double read_write_ratio;
  double ins_del_ratio;
  size_t total_operations;
} OperationMix;

typedef struct
{
  double total_time;
  size_t operations_done;
  double ops_per_second;
  uint64_t checksum;
  uint64_t cycles_per_op;  
} BenchmarkResult;

typedef struct
{
  void *data_structure;
  int (*get)(void *ds, size_t index);
  void (*set)(void *ds, size_t index, int value);
  void (*insert)(void *ds, size_t index, int value);
  void (*delete)(void *ds, size_t index);
  void (*destroy)(void *ds);  
  size_t *current_size;
} DataStructure;

BenchmarkResult run_benchmark(DataStructure *ds, OperationMix *mix);
void print_benchmark_result(BenchmarkResult *result);

#endif
