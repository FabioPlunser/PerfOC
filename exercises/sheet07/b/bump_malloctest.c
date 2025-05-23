#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <inttypes.h>
#include <string.h> // For memset if you were to keep it, but calloc handles zeroing

// Using a slightly larger arena or being mindful of exact max usage
#define ARENA_SIZE_BYTES (1200LL * 1024 * 1024) // 1.2GB arena

// Bump allocator structure
typedef struct {
    char* buffer;         
    size_t size;          
    size_t used;          
    pthread_mutex_t lock; 
} bump_allocator_t;

bump_allocator_t allocator;

void init_bump_allocator() {
    allocator.buffer = malloc(ARENA_SIZE_BYTES);
    if (!allocator.buffer) {
        perror("Failed to allocate arena buffer");
        exit(EXIT_FAILURE);
    }
    allocator.size = ARENA_SIZE_BYTES;
    allocator.used = 0;
    pthread_mutex_init(&allocator.lock, NULL);
}

void destroy_bump_allocator() {
    if (allocator.buffer) {
        free(allocator.buffer);
    }
    pthread_mutex_destroy(&allocator.lock);
}

void* bump_malloc(size_t size) {
    if (size == 0) size = 1; 

    pthread_mutex_lock(&allocator.lock);
    
    // Align to 8 bytes (or more, e.g., _Alignof(max_align_t))
    size_t effective_size = (size + 7) & ~7; 
    char* current_ptr = allocator.buffer + allocator.used;
    uintptr_t aligned_addr_val = ((uintptr_t)current_ptr + 7) & ~7;
    char* aligned_ptr = (char*)aligned_addr_val;

    // Calculate padding introduced by alignment
    size_t padding = aligned_ptr - current_ptr;
    
    if (allocator.used + padding + effective_size > allocator.size) {
        pthread_mutex_unlock(&allocator.lock);
        fprintf(stderr, "Bump allocator OOM: requested %zu, effective %zu, used %zu, arena %zu\n",
                size, effective_size, allocator.used, allocator.size);
        return NULL; 
    }
    
    // Allocate memory
    allocator.used += padding + effective_size;
    
    pthread_mutex_unlock(&allocator.lock);
    return (void*)aligned_ptr;
}

// Reset the bump allocator (free all memory at once)
void bump_reset() {
    pthread_mutex_lock(&allocator.lock);
    allocator.used = 0;
    pthread_mutex_unlock(&allocator.lock);
}

void bump_free(void* ptr) {
    (void)ptr;
}

typedef struct {
    int64_t repeats;
    int64_t iterations;
    int64_t lower, upper;
} thread_args;

void* benchmark_thread(void *args) {
    thread_args *t_args = (thread_args*)args;
    // Per-thread seed, can be made more unique if needed
    unsigned int seed = (unsigned int)pthread_self(); 

    for(int64_t r = 0; r < t_args->repeats; ++r) {
        // CRITICAL: Reset the bump allocator for each repeat cycle
        // This allows the same arena space to be reused.
        if (t_args->repeats > 1 || r == 0) { 
             bump_reset();
        }

        void **allocations = (void**)calloc(t_args->iterations, sizeof(void*));
        if (!allocations) {
            perror("calloc for allocations array failed");
            return (void*)-1; // Indicate error
        }
        
        
        for(int64_t i = 0; i < t_args->iterations; ++i) {
            int64_t to_alloc = rand_r(&seed) % (t_args->upper - t_args->lower + 1) + t_args->lower;
            allocations[i] = bump_malloc(to_alloc);
            if (allocations[i] == NULL && to_alloc > 0) {
                fprintf(stderr, "Thread %p: bump_malloc failed for size %" PRId64 " on iter %" PRId64 ", repeat %" PRId64 "\n",
                        (void*)pthread_self(), to_alloc, i, r);
                free(allocations); 
                return (void*)-1; 
            }
        }
        
        
        free(allocations); 
    }
    return NULL;
}

int main(int argc, char** argv) {
    int64_t num_threads = 1; 
    if(argc != 6) {
        printf("USAGE: ./malloctest [num_threads] [num_repeats] [num_iterations] [lower] [upper]\n");
        return -1;
    }
    num_threads = atol(argv[1]);
    thread_args t_args;
    t_args.repeats = atol(argv[2]);
    t_args.iterations = atol(argv[3]);
    t_args.lower = atol(argv[4]);
    t_args.upper = atol(argv[5]);

    init_bump_allocator();
    
    pthread_t* threads = (pthread_t*)calloc(num_threads, sizeof(pthread_t));
    if (!threads) {
        perror("calloc for threads array failed");
        destroy_bump_allocator();
        return -1;
    }
    
    for(int64_t i = 0; i < num_threads; ++i) {
        if (pthread_create(&threads[i], NULL, benchmark_thread, &t_args) != 0) {
            perror("Failed to create thread");
            free(threads);
            destroy_bump_allocator();
            return -1;
        }
    }

    for(int64_t i = 0; i < num_threads; ++i) {
        void* thread_ret_val;
        if (pthread_join(threads[i], &thread_ret_val) != 0) {
            perror("Failed to join thread");
        }
        if (thread_ret_val == (void*)-1) {
            fprintf(stderr, "A benchmark thread reported an error.\n");
        }
    }
    
    free(threads); 
    destroy_bump_allocator(); 
    
    return 0;
}

