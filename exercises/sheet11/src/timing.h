#ifndef TIMING_UTILS_H
#define TIMING_UTILS_H
#define _POSIX_C_SOURCE 200809L

#include <time.h>

// Structure to hold start and end times
typedef struct {
    struct timespec start_time;
    struct timespec end_time;
} timing_info;

// Start the timer
void start_timer(timing_info *timer);

// Stop the timer
void stop_timer(timing_info *timer);

// Get elapsed time in seconds
double get_elapsed_seconds(timing_info *timer);

// Get elapsed time in nanoseconds
long long get_elapsed_nanoseconds(timing_info *timer);

#endif // TIMING_UTILS_H