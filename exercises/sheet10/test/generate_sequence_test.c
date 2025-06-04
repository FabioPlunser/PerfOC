#include "../lib/benchmark.h"
#include "../lib/args_parser.h"
#include "../lib/container_registry.h"

#include <stdio.h>
#include <stdlib.h>

// Test the sequence generation function from 0.0 to 1.0 ratio
void test_sequence_generation()
{
    // Summary statistics
    double total_r = 0, total_w = 0, total_i = 0, total_d = 0;
    int min_balance = 0, max_balance = 0;
    int max_inserts = 0;
    int test_count = 0;

    for (double ratio = 0.0; ratio <= 1.0; ratio += 0.1)
    {
        size_t length = 100;
        unsigned char *sequence = generate_sequence(ratio, length);

        size_t r_count, w_count, i_count, d_count;
        int insert_balance, max_consecutive_inserts;
        validate_sequence(sequence, length, &r_count, &w_count, &i_count, &d_count,
                          &insert_balance, &max_consecutive_inserts);

        printf("Ratio: %.1f | R: %zu W: %zu I: %zu D: %zu | Balance: %d | Max Consecutive Inserts: %d\n",
               ratio, r_count, w_count, i_count, d_count,
               insert_balance, max_consecutive_inserts);

        // Update summary statistics
        total_r += r_count;
        total_w += w_count;
        total_i += i_count;
        total_d += d_count;
        if (test_count == 0 || insert_balance < min_balance)
            min_balance = insert_balance;
        if (test_count == 0 || insert_balance > max_balance)
            max_balance = insert_balance;
        if (max_consecutive_inserts > max_inserts)
            max_inserts = max_consecutive_inserts;
        test_count++;

        free(sequence);
    }

    // Print summary
    printf("\n--- Summary ---\n");
    printf("Tests run: %d\n", test_count);
    printf("Average operations: R: %.2f W: %.2f I: %.2f D: %.2f\n",
           total_r / test_count, total_w / test_count, total_i / test_count, total_d / test_count);
    printf("Balance range: %d to %d\n", min_balance, max_balance);
    printf("Maximum consecutive inserts: %d\n", max_inserts);
}

int main()
{
    printf("Testing sequence generation...\n");
    test_sequence_generation();
    printf("All tests completed successfully.\n");
    return 0;
}
