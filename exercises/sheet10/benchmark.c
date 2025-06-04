#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <stdbool.h>
#include "benchmark.h"
#include "args_parser.h"
#include "container_registry.h"


size_t get_next_index(size_t current, size_t size)
{
    return (current + 1) % (size > 0 ? size : 1);
}

int *create_random_indices(size_t length) {
    int *random_indices = malloc(length * sizeof(int));

    if (random_indices == NULL) {
        fprintf(stderr, "Failed to allocate memory for random indices");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < length; i++) random_indices[i] = i;
    srand(time(NULL));
    
    //shuffle indices
    for (int i = length - 1; i > 0; i--) {
        int j = rand() % (i+1);
        int tmp = random_indices[j];
        random_indices[j] = random_indices[i];
        random_indices[i] = tmp;
    }

    return random_indices;
}

double run_benchmark(Benchmark *benchmark, double seconds, int randomize_access)
{
    Container *container = &benchmark->container;

    container->init(container->data, benchmark->container_size, benchmark->container.element_size);

    //if flag is set randomize the indices that get accessed by the benchmark
    int *random_indices = NULL;
    if (randomize_access){
        random_indices = create_random_indices(benchmark->container_size);
    }

    struct timeval start_time, current_time;
    gettimeofday(&start_time, NULL);

    size_t current_size = benchmark->container_size;
    size_t current_index = 0;
    size_t operations_completed = 0;
    volatile int result_accumulator = 0;

    long long target_end_us = start_time.tv_sec * 1000000LL + start_time.tv_usec +
                              (long long)(seconds * 1000000.0);
    long long current_time_us = start_time.tv_sec * 1000000LL + start_time.tv_usec;

    while (current_time_us < target_end_us)
    {
        // Run a batch of operations before checking time again
        size_t batch_size = 32;
        for (size_t i = 0; i < batch_size && current_time_us < target_end_us; i++)
        {
            unsigned char op = benchmark->operation_sequence[operations_completed % benchmark->sequence_length];

            if (current_size == 0)
                current_size = 1;
            
            size_t safe_index = current_index % current_size;
            if (randomize_access && random_indices) {
                safe_index = random_indices[current_index] % current_size;
            }

            switch (op)
            {
            case 0: // Read
            {
                int value = container->read(container->data, safe_index);
                result_accumulator += value;
                current_index = (current_index + 1) % current_size;
            }
            break;

            case 1: // Write
            {
                int value = rand() % 10000;
                container->write(container->data, safe_index, value);
                current_index = (current_index + 1) % current_size;
            }
            break;

            case 2: // Insert
            {
                int value = rand() % 10000;
                int success = container->insert(container->data, safe_index, value);
                if (success == 0)
                {
                    current_size++;
                }
                current_index = (current_index + 1) % current_size;
            }
            break;

            case 3: // Delete
            {
                if (current_size > 1)
                {
                    int success = container->delete(container->data, safe_index);
                    if (success == 0)
                    {
                        current_size--;
                    }
                }
                current_index = current_index % current_size;
            }
            break;
            }

            operations_completed++;
            //printf("\rOperations completed: %zu", operations_completed);
            //fflush(stdout);
        }

        gettimeofday(&current_time, NULL);
        current_time_us = current_time.tv_sec * 1000000LL + current_time.tv_usec;
    }
    printf("\n");
    double elapsed = (current_time.tv_sec - start_time.tv_sec) +
                     (current_time.tv_usec - start_time.tv_usec) / 1000000.0;

    printf("Validation checksum: %d\n", result_accumulator);
    printf("Actual benchmark time: %.3f seconds (target: %.1f)\n", elapsed, seconds);
    container->cleanup(container->data);

    #ifdef _RANDOM_ACCESS
    free(random_indices);
    #endif

    return (double)operations_completed / elapsed;
}

int main(int argc, char *argv[])
{
    srand(time(NULL));

    init_container_registry();

    BenchmarkArgs args;
    if (parse_benchmark_args(argc, argv, &args) != 0)
    {
        cleanup_container_registry();
        printf("Error parsing arguments.\n");
        return 1;
    }

    Benchmark benchmark;
    if (initialize_benchmark(&args, &benchmark) != 0)
    {
        cleanup_container_registry();
        printf("Error initializing benchmark.\n");
        return 1;
    }

    printf("\nRunning benchmark for %.1f seconds on container with %zu elements of size %zu bytes\n",
           args.benchmark_seconds, args.num_elements, args.element_size);
    printf("Insert/Delete to Read/Write ratio: %.2f\n", args.ratio);

    double ops_per_second = run_benchmark(&benchmark, args.benchmark_seconds, args.randomize_access);

    printf("\nBenchmark Results:\n");
    printf("Operations per second: %.2f\n", ops_per_second);

    free(benchmark.operation_sequence);
    free(benchmark.container.data);

    cleanup_container_registry();

    return 0;
}