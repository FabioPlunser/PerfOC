#ifndef ARGS_PARSER_H
#define ARGS_PARSER_H

#include <stddef.h>
#include "benchmark.h"

typedef struct
{
    char container_type[32];  // Type of container (array, linkedlist_seq, linkedlist_rand)
    size_t num_elements;      // Initial number of elements in container
    size_t element_size;      // Size of each element in bytes
    double ratio;             // Ratio of insert/delete operations to read/write operations
    double benchmark_seconds; // Duration of benchmark in seconds
    int randomize_access;     // Randomize the access pattern of the benchmark
} BenchmarkArgs;

int parse_benchmark_args(int argc, char *argv[], BenchmarkArgs *args);
int initialize_benchmark(const BenchmarkArgs *args, Benchmark *benchmark);
void print_statistics(size_t i_count, size_t d_count, size_t length, size_t r_count, size_t w_count,
                      double ins_del_ratio, double read_ratio, int insert_balance, int max_consecutive_inserts,
                      unsigned char *sequence);
void validate_sequence(unsigned char *sequence, size_t length,
                       size_t *r_count, size_t *w_count, size_t *i_count, size_t *d_count,
                       int *insert_balance, int *max_consecutive_inserts);
unsigned char *generate_sequence(double ins_del_ratio, size_t length);

#endif // ARGS_PARSER_H