#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "args_parser.h"
#include "benchmark.h"
#include "container_registry.h"

unsigned char *generate_sequence(double ratio, size_t length)
{
    unsigned char *sequence = malloc(length * sizeof(unsigned char));
    if (!sequence)
    {
        fprintf(stderr, "Failed to allocate memory for operation sequence\n");
        exit(1);
    }

    size_t ins_del_ops = (size_t)(length * ratio);
    if (ins_del_ops % 2 != 0)
    {
        ins_del_ops = (ins_del_ops > 0) ? ins_del_ops - 1 : 0;
    }

    size_t insert_ops = ins_del_ops / 2;
    size_t delete_ops = ins_del_ops / 2;
    size_t read_write_ops = length - ins_del_ops;

    size_t read_ops = read_write_ops / 2;
    size_t write_ops = read_write_ops - read_ops;

    printf("**Target Operation Distribution:**\n");
    printf("    Insert Operations: %zu (%.1f%%)\n", insert_ops, 100.0 * insert_ops / length);
    printf("    Delete Operations: %zu (%.1f%%)\n", delete_ops, 100.0 * delete_ops / length);
    printf("    Read Operations: %zu (%.1f%%)\n", read_ops, 100.0 * read_ops / length);
    printf("    Write Operations: %zu (%.1f%%)\n", write_ops, 100.0 * write_ops / length);
    printf("    Total Length: %zu operations\n\n", length);

    // Flip-flop states
    int id_state = 1; // Start with insert (1=insert, 0=delete)
    int rw_state = 1; // Start with read (1=read, 0=write)

    size_t placed_inserts = 0;
    size_t placed_deletes = 0;
    size_t placed_reads = 0;
    size_t placed_writes = 0;

    // Generate sequence
    for (size_t i = 0; i < length; i++)
    {
        size_t remaining_ops = length - i;
        size_t remaining_id = (insert_ops - placed_inserts) + (delete_ops - placed_deletes);
        size_t remaining_rw = (read_ops - placed_reads) + (write_ops - placed_writes);

        double id_probability = (remaining_id > 0 && remaining_rw > 0) ? (double)remaining_id / remaining_ops : (remaining_id > 0) ? 1.0
                                                                                                                                   : 0.0;

        if ((remaining_id > 0 && remaining_rw == 0) ||
            (remaining_id > 0 && remaining_rw > 0 &&
             (double)rand() / RAND_MAX < id_probability))
        {
            // Place insert/delete operation
            if (id_state == 1 && placed_inserts < insert_ops)
            {
                sequence[i] = 2; // Insert
                placed_inserts++;
                id_state = 0;
            }
            else if (id_state == 0 && placed_deletes < delete_ops)
            {
                sequence[i] = 3; // Delete
                placed_deletes++;
                id_state = 1;
            }
            else if (placed_inserts < insert_ops)
            {
                // Forced insert if no deletes left
                sequence[i] = 2;
                placed_inserts++;
                id_state = 0;
            }
            else if (placed_deletes < delete_ops)
            {
                // Forced delete if no inserts left
                sequence[i] = 3;
                placed_deletes++;
                id_state = 1;
            }
        }
        else if (remaining_rw > 0)
        {
            // Place read/write operation
            if (rw_state == 1 && placed_reads < read_ops)
            {
                sequence[i] = 0; // Read
                placed_reads++;
                rw_state = 0;
            }
            else if (rw_state == 0 && placed_writes < write_ops)
            {
                sequence[i] = 1; // Write
                placed_writes++;
                rw_state = 1;
            }
            else if (placed_reads < read_ops)
            {
                sequence[i] = 0;
                placed_reads++;
                rw_state = 0;
            }
            else if (placed_writes < write_ops)
            {
                sequence[i] = 1;
                placed_writes++;
                rw_state = 1;
            }
        }
        else
        {
            // Should not happen, but default to read
            sequence[i] = 0;
        }
    }

    size_t r_count, w_count, i_count, d_count;
    int insert_balance, max_consecutive_inserts;

    validate_sequence(sequence, length, &r_count, &w_count, &i_count, &d_count,
                      &insert_balance, &max_consecutive_inserts);
    print_statistics(i_count, d_count, length, r_count, w_count,
                     ratio, 0.5, insert_balance,
                     max_consecutive_inserts, sequence);

    return sequence;
}

int parse_benchmark_args(int argc, char *argv[], BenchmarkArgs *args)
{
    if (argc > 1 && strcmp(argv[1], "--list-containers") == 0)
    {
        list_available_containers();
        exit(0);
    }

    if (argc < 5)
    {
        printf("Usage: %s <container_type> <num_elements> <element_size> <read_ratio> [benchmark_seconds] [randomize_access]\n", argv[0]);
        printf("       %s --list-containers\n", argv[0]);
        return 1;
    }

    strncpy(args->container_type, argv[1], sizeof(args->container_type) - 1);
    args->container_type[sizeof(args->container_type) - 1] = '\0';

    args->num_elements = strtoul(argv[2], NULL, 10);
    args->element_size = strtoul(argv[3], NULL, 10);
    args->ratio = strtod(argv[4], NULL);
    args->benchmark_seconds = (argc > 4) ? strtod(argv[5], NULL) : 5.0;
    args->randomize_access = (argc > 5) ? strtoul(argv[6], NULL, 10) : 0;

    return 0;
}

int initialize_benchmark(const BenchmarkArgs *args, Benchmark *benchmark)
{
    benchmark->container_size = args->num_elements;
    benchmark->ratio = args->ratio;

    benchmark->operation_sequence = generate_sequence(args->ratio, args->num_elements);
    benchmark->sequence_length = args->num_elements;

    Container *container = create_container_by_name(args->container_type);
    if (!container)
    {
        printf("Unknown container type '%s'. Use --list-containers to see options.\n", args->container_type);
        free(benchmark->operation_sequence);
        return 1;
    }

    benchmark->container = *container;
    free(container);

    benchmark->container.element_size = args->element_size;
    printf("Using container: %s\n", args->container_type);
    printf("Container size: %zu\n", benchmark->container_size);
    printf("Element size: %zu\n", benchmark->container.element_size);
    printf("Total Memory: %zu bytes -> %zu MB\n", benchmark->container_size * benchmark->container.element_size,
           (benchmark->container_size * benchmark->container.element_size) / (1024 * 1024));

    return 0;
}

const char *get_operation_emoji_structural(unsigned char op)
{
    switch (op)
    {
    case 0:
        return "📖"; // Read operation
    case 1:
        return "✏️ "; // Write operation
    case 2:
        return "🧩"; // Insert operation
    case 3:
        return "❌"; // Delete operation
    default:
        return "❓"; // Unknown operation
    }
}

void print_statistics(size_t i_count, size_t d_count, size_t length, size_t r_count, size_t w_count, double ins_del_ratio, double read_ratio, int insert_balance, int max_consecutive_inserts, unsigned char *sequence)
{
    double actual_ins_del_ratio = (i_count + d_count) / (double)length;
    double actual_read_ratio = (r_count + w_count > 0) ? r_count / (double)(r_count + w_count) : 0.0;

    printf("**Final Operation Statistics:**\n");
    printf("    Insert Operations: %zu (%.1f%%)\n", i_count, 100.0 * i_count / length);
    printf("    Delete Operations: %zu (%.1f%%)\n", d_count, 100.0 * d_count / length);
    printf("    Read Operations: %zu (%.1f%%)\n", r_count, 100.0 * r_count / length);
    printf("    Write Operations: %zu (%.1f%%)\n", w_count, 100.0 * w_count / length);
    printf("    Requested ins/del ratio: %.2f → Actual: %.2f\n", ins_del_ratio, actual_ins_del_ratio);
    printf("    Requested read ratio: %.2f → Actual: %.2f\n", read_ratio, actual_read_ratio);
    printf("    Insert-Delete Balance: %s\n", (insert_balance == 0 && i_count == d_count) ? "✅ PERFECT" : "⚠️ IMBALANCED");
    printf("    Max Consecutive Inserts: %d %s\n", max_consecutive_inserts, (max_consecutive_inserts <= 1) ? "✅ CONSTRAINT SATISFIED" : "❌ CONSTRAINT VIOLATED");

    //printf("\n**Operation Sequence:**\n   ");
    //for (size_t i = 0; i < length; i++)
    //{
    //    printf("%s ", get_operation_emoji_structural(sequence[i]));
    //    if ((i + 1) % 20 == 0)
    //        printf("\n   ");
    //}
    //printf("\n");
    printf("\n**Operation Sequence (first 50 operations):**\n   ");
    for (size_t i = 0; i < length && i < 50; i++)
    {
        printf("%s ", get_operation_emoji_structural(sequence[i]));
        if ((i + 1) % 20 == 0)
            printf("\n   ");
    }
    if (length > 50)
        printf("\n   ... (total %zu operations)\n", length);
    else
        printf("\n");
}
void validate_sequence(unsigned char *sequence, size_t length,
                       size_t *r_count, size_t *w_count, size_t *i_count, size_t *d_count,
                       int *insert_balance, int *max_consecutive_inserts)
{
    *r_count = 0;
    *w_count = 0;
    *i_count = 0;
    *d_count = 0;
    *insert_balance = 0;
    *max_consecutive_inserts = 0;
    int current_consecutive = 0;
    int open_inserts = 0;

    printf("**Sequence Validation:**\n");

    int last_id_op = -1; // -1=none, 2=insert, 3=delete
    int last_rw_op = -1; // -1=none, 0=read, 1=write
    int id_alternation_violations = 0;
    int rw_alternation_violations = 0;

    for (size_t i = 0; i < length; i++)
    {
        unsigned char op = sequence[i];

        // Count operations
        switch (op)
        {
        case 0:
            (*r_count)++;
            if (last_rw_op == 0)
                rw_alternation_violations++;
            last_rw_op = 0;
            break;
        case 1:
            (*w_count)++;
            if (last_rw_op == 1)
                rw_alternation_violations++;
            last_rw_op = 1;
            break;
        case 2:
            (*i_count)++;
            (*insert_balance)++;
            current_consecutive++;
            open_inserts++;
            if (current_consecutive > *max_consecutive_inserts)
            {
                *max_consecutive_inserts = current_consecutive;
            }
            if (last_id_op == 2)
                id_alternation_violations++;
            last_id_op = 2;
            break;
        case 3:
            (*d_count)++;
            (*insert_balance)--;
            current_consecutive = 0;
            if (open_inserts > 0)
                open_inserts--;
            if (last_id_op == 3)
                id_alternation_violations++;
            last_id_op = 3;
            break;
        }

        if (op != 2)
        {
            current_consecutive = 0;
        }
    }

    printf("    I/D Alternation Violations: %d %s\n",
           id_alternation_violations,
           id_alternation_violations == 0 ? "✅ PERFECT" : "⚠️ DETECTED");
    printf("    R/W Alternation Violations: %d %s\n",
           rw_alternation_violations,
           rw_alternation_violations == 0 ? "✅ PERFECT" : "⚠️ DETECTED");
    printf("    Open Insert Operations: %d %s\n",
           open_inserts,
           open_inserts == 0 ? "✅ ALL CLOSED" : "⚠️ UNCLOSED");
    printf("\n");
}