#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "timing.h"
//------------------------------------------------------------------------------
typedef unsigned long dn;

typedef struct
{
	dn x, y;
	dn result;
} memo_entry;

typedef struct
{
	memo_entry *entries;
	int size;
	int capacity;
} memo_table;
//------------------------------------------------------------------------------
memo_table *create_memo_table(int capacity)
{
	if (capacity <= 0)
	{
		fprintf(stderr, "Error: Memo table capacity must be positive.\n");
		return NULL;
	}
	memo_table *table = malloc(sizeof(memo_table));
	if (table == NULL)
	{
		perror("Failed to allocate memo_table struct");
		return NULL;
	}
	table->entries = calloc(capacity, sizeof(memo_entry));
	if (table->entries == NULL)
	{

		perror("Failed to allocate memo_table entries");
		free(table);
		return NULL;
	}
	table->size = 0;
	table->capacity = capacity;
	return table;
}

int hash_function(dn x, dn y, int capacity)
{
	if (capacity == 0)
		return 0;
	return (int)(((x * 31 + y)) % (unsigned int)capacity);
}

dn lookup_memo(memo_table *table, dn x, dn y)
{
	if (table == NULL || table->capacity == 0)
		return 0;

	int hash = hash_function(x, y, table->capacity);
	int original_hash = hash;

	// Loop while the current slot is not an empty slot (marked by x=0 and y=0 from calloc)
	while (table->entries[hash].x != 0 || table->entries[hash].y != 0)
	{
		if (table->entries[hash].x == x && table->entries[hash].y == y)
		{
			return table->entries[hash].result;
		}
		hash = (hash + 1) % table->capacity;
		if (hash == original_hash)
		{
			break;
		}
	}
	return 0;
}

void store_memo(memo_table *table, dn x, dn y, dn result)
{
	if (table == NULL)
		return;

	// Check if table is full before trying to find a slot
	if (table->size >= table->capacity)
	{
		fprintf(stderr,
						"Error: Memoization table full. Capacity: %d, Size: %d. Cannot "
						"store (%lu, %lu).\n",
						table->capacity, table->size, x, y);
		return;
	}

	if (table->capacity == 0)
		return; // Cannot store

	int hash = hash_function(x, y, table->capacity);
	int original_hash = hash;

	// Find an empty slot (where .x and .y are both 0, due to calloc)
	// This loop is guaranteed to find an empty slot if table->size < table->capacity
	while (table->entries[hash].x != 0 || table->entries[hash].y != 0)
	{
		hash = (hash + 1) % table->capacity;
		if (hash == original_hash)
		{
			fprintf(stderr,
							"Error: store_memo cycled through table, implies table is "
							"full or logic error.\n");
			return;
		}
	}

	table->entries[hash].x = x;
	table->entries[hash].y = y;
	table->entries[hash].result = result;
	table->size++;
}
//------------------------------------------------------------------------------
memo_table *memo;

dn delannoy_memo(dn x, dn y)
{
	if (x == 0 || y == 0)
		return 1;

	dn cached = lookup_memo(memo, x, y);

	// If cached is non-zero, it means the value was found.
	if (cached != 0)
		return cached;

	dn a = delannoy_memo(x - 1, y);
	dn b = delannoy_memo(x - 1, y - 1);
	dn c = delannoy_memo(x, y - 1);

	dn result = a + b + c;
	store_memo(memo, x, y, result);

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
		printf("Usage: delannoy N\n");
		exit(EXIT_FAILURE);
	}

	int n = atoi(argv[1]);

	if (n >= NUM_RESULTS)
	{
		printf("N too large (can only check up to %d)\n", NUM_RESULTS);
		exit(-1);
	}

	int max_n_val = NUM_RESULTS - 1;
	int max_items_to_store = (max_n_val > 0) ? (max_n_val * max_n_val) : 0;

	int table_capacity = max_items_to_store * 2;

	memo = create_memo_table(table_capacity);
	if (memo == NULL)
	{
		exit(EXIT_FAILURE);
	}

	timing_info internal_timer;
	start_timer(&internal_timer);

	dn result = delannoy_memo(n, n);

	stop_timer(&internal_timer);
	printf("Internal_Time_ns: %lld\n", get_elapsed_nanoseconds(&internal_timer));
	printf("Internal_Time_s: %.9f\n", get_elapsed_seconds(&internal_timer));

	int exit_status = EXIT_FAILURE;
	if (result == DELANNOY_RESULTS[n])
	{
		printf("Verification: OK\n");
		exit_status = EXIT_SUCCESS;
	}
	else
	{
		printf("Verification: ERR\n");
		printf("Expected: %lu, Got: %lu for n=%d\n", DELANNOY_RESULTS[n],
					 result, n);
	}

	if (memo != NULL)
	{
		free(memo->entries);
		free(memo);
	}

	return exit_status;
}