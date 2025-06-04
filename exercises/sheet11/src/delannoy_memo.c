#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "shared.h"

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
	memo_table *table = malloc(sizeof(memo_table));
	table->entries = calloc(capacity, sizeof(memo_entry));
	table->size = 0;
	table->capacity = capacity;
	return table;
}

int hash_function(dn x, dn y, int capacity)
{
	return ((x * 31 + y) % capacity);
}

dn lookup_memo(memo_table *table, dn x, dn y)
{
	int hash = hash_function(x, y, table->capacity);
	int original_hash = hash;

	while (table->entries[hash].x != 0 || table->entries[hash].y != 0)
	{
		if (table->entries[hash].x == x && table->entries[hash].y == y)
		{
			return table->entries[hash].result;
		}
		hash = (hash + 1) % table->capacity;
		if (hash == original_hash)
			break;
	}
	return 0;
}

void store_memo(memo_table *table, dn x, dn y, dn result)
{
	int hash = hash_function(x, y, table->capacity);

	while (table->entries[hash].x != 0 || table->entries[hash].y != 0)
	{
		hash = (hash + 1) % table->capacity;
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
	if (cached != 0 || (x == 0 && y == 0))
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
	result = delannoy_memo(n, n);

	if (result == DELANNOY_RESULTS[n])
	{
		printf("Verification: OK\n");
		return EXIT_SUCCESS;
	}
	printf("Verification: ERR\n");
	return EXIT_FAILURE;
}
