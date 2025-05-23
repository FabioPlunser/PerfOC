#include "timing.h"

#ifdef _WIN32
#include <windows.h>
double get_time()
{
  LARGE_INTEGER freq, counter;
  QueryPerformanceFrequency(&freq);
  QueryPerformanceCounter(&counter);
  return (double)counter.QuadPart / freq.QuadPart;
}
uint64_t get_cycles()
{
  return 0;
}
#else
#include <time.h>
double get_time()
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec + ts.tv_nsec / 1e9;
}
#ifdef __x86_64__
uint64_t get_cycles()
{
  uint32_t lo, hi;
  __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
  return ((uint64_t)hi << 32) | lo;
}
#else
uint64_t get_cycles()
{
  return 0;
}
#endif
#endif
