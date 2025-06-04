#include "timing.h"
#include <stdio.h> 
#include <time.h>

void start_timer(timing_info *timer) {
    if (clock_gettime(CLOCK_MONOTONIC, &timer->start_time) == -1) {
        perror("clock_gettime start");
    }
}

void stop_timer(timing_info *timer) {
    if (clock_gettime(CLOCK_MONOTONIC, &timer->end_time) == -1) {
        perror("clock_gettime stop");
    }
}

double get_elapsed_seconds(timing_info *timer) {
    double seconds = (timer->end_time.tv_sec - timer->start_time.tv_sec);
    seconds += (timer->end_time.tv_nsec - timer->start_time.tv_nsec) / 1000000000.0;
    return seconds;
}

long long get_elapsed_nanoseconds(timing_info *timer) {
    long long ns = (timer->end_time.tv_sec - timer->start_time.tv_sec) * 1000000000LL;
    ns += (timer->end_time.tv_nsec - timer->start_time.tv_nsec);
    return ns;
}