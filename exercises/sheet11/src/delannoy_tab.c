#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "timing.h"

typedef unsigned long dn;

dn delannoy_tabulation(dn x, dn y)
{
  if (x == 0 || y == 0)
    return 1;

  dn *prev_row = calloc(x + 1, sizeof(dn));
  dn *curr_row = calloc(x + 1, sizeof(dn));

  // Initialize base cases
  for (dn i = 0; i <= x; i++)
  {
    prev_row[i] = 1;
  }

  // Fill table row by row
  for (dn j = 1; j <= y; j++)
  {
    curr_row[0] = 1;

    for (dn i = 1; i <= x; i++)
    {
      curr_row[i] = prev_row[i] +
                    prev_row[i - 1] +
                    curr_row[i - 1];
    }

    // Swap rows
    dn *temp = prev_row;
    prev_row = curr_row;
    curr_row = temp;
  }

  dn result = prev_row[x];

  free(prev_row);
  free(curr_row);

  return result;
}

dn DELANNOY_RESULTS[] = {
    1, 3, 13, 63, 321, 1683, 8989, 48639, 265729, 1462563, 8097453, 45046719, 251595969, 1409933619,
    7923848253, 44642381823, 252055236609, 1425834724419, 8079317057869, 45849429914943, 260543813797441,
    1482376214227923, 8443414161166173};

int NUM_RESULTS = sizeof(DELANNOY_RESULTS) / sizeof(dn);

int main(int argc, char **argv)
{
  if (argc < 2)
  {
    printf("Usage: delannoy N [+t]\n");
    exit(-1);
  }

  int n = atoi(argv[1]);
  if (n >= NUM_RESULTS)
  {
    printf("N too large (can only check up to %d)\n", NUM_RESULTS);
    exit(-1);
  }

  dn result = 0;
  timing_info internal_timer;
  start_timer(&internal_timer);

  result = delannoy_tabulation(n, n);

  stop_timer(&internal_timer);
  printf("Internal_Time_ns: %lld\n", get_elapsed_nanoseconds(&internal_timer));
  printf("Internal_Time_s: %.9f\n", get_elapsed_seconds(&internal_timer));

  if (result == DELANNOY_RESULTS[n])
  {
    printf("Verification: OK\n");
    return EXIT_SUCCESS;
  }
  printf("Verification: ERR\n");
  return EXIT_FAILURE;
}
