#include "benchmark.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdbool.h>

// Forward declarations
DataStructure create_array(size_t initial_size);
DataStructure create_linkedlist(size_t initial_size, bool random_alloc);

int main(int argc, char **argv)
{
  if (argc != 5)
  {
    fprintf(stderr, "Usage: %s <data_structure> <num_elements> <read_write_ratio> <ins_del_ratio>\n", argv[0]);
    fprintf(stderr, "data_structure: array, list_seq, list_rand\n");
    return 1;
  }

  srand(time(NULL));

  char *ds_type = argv[1];
  size_t num_elements = atoi(argv[2]);
  double read_write_ratio = atof(argv[3]);
  double ins_del_ratio = atof(argv[4]);

  // Scale operations based on data structure size
  size_t total_ops;
  if (num_elements <= 10)
  {
    total_ops = 100000;
  }
  else if (num_elements <= 100)
  {
    total_ops = 1000000;
  }
  else
  {
    total_ops = 10000000;
  }

  DataStructure ds;
  if (strcmp(ds_type, "array") == 0)
  {
    ds = create_array(num_elements);
  }
  else if (strcmp(ds_type, "list_seq") == 0)
  {
    ds = create_linkedlist(num_elements, false);
  }
  else if (strcmp(ds_type, "list_rand") == 0)
  {
    ds = create_linkedlist(num_elements, true);
  }
  else
  {
    fprintf(stderr, "Unknown data structure: %s\n", ds_type);
    return 1;
  }

  OperationMix mix = {
      .read_write_ratio = read_write_ratio,
      .ins_del_ratio = ins_del_ratio,
      .total_operations = total_ops};

  printf("Benchmarking %s: %zu elements, %.1f%% read/write, %.1f%% ins/del, %zu ops\n",
         ds_type, num_elements, read_write_ratio * 100, ins_del_ratio * 100, total_ops);

  BenchmarkResult result = run_benchmark(&ds, &mix);
  print_benchmark_result(&result);

  ds.destroy(ds.data_structure);
  return 0;
}
