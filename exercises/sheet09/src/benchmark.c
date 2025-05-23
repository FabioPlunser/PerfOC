#include "benchmark.h"
#include "timing.h"
#include <stdio.h>
#include <stdlib.h>

// Generate operations with MINIMUM SPACING as required
void generate_operations_minimum_spacing(OperationType *ops, OperationMix *mix)
{
    size_t total = mix->total_operations;
    size_t ins_del_count = (size_t)(total * mix->ins_del_ratio);
    size_t read_write_count = total - ins_del_count;

    size_t read_count = (size_t)(read_write_count * mix->read_write_ratio);
    size_t write_count = read_write_count - read_count;
    size_t insert_count = ins_del_count / 2;
    size_t delete_count = ins_del_count - insert_count;

    // Create the minimum spacing pattern
    // For 20% ins/del, 80% read/write with 50/50 splits:
    // Pattern: read, write, read, write, insert, read, write, read, write, delete

    size_t pattern_length = 0;
    if (ins_del_count > 0)
    {
        // Calculate pattern length for minimum spacing
        size_t rw_per_id = read_write_count / ins_del_count;
        pattern_length = rw_per_id + 1; // +1 for the ins/del operation
    }
    else
    {
        pattern_length = total;
    }

    size_t pos = 0;
    size_t reads_placed = 0, writes_placed = 0;
    size_t inserts_placed = 0, deletes_placed = 0;

    while (pos < total)
    {
        // Place read/write operations before next ins/del
        size_t rw_in_this_segment = (pos + pattern_length <= total) ? pattern_length - 1 : total - pos - 1;

        // Distribute reads and writes evenly in this segment
        for (size_t i = 0; i < rw_in_this_segment && pos < total; i++)
        {
            if (reads_placed < read_count &&
                (writes_placed >= write_count || (i % 2 == 0)))
            {
                ops[pos++] = OP_READ;
                reads_placed++;
            }
            else if (writes_placed < write_count)
            {
                ops[pos++] = OP_WRITE;
                writes_placed++;
            }
            else if (reads_placed < read_count)
            {
                ops[pos++] = OP_READ;
                reads_placed++;
            }
            else
            {
                pos++; // Skip if we've placed all read/write ops
            }
        }

        // Place one ins/del operation (alternating)
        if (pos < total && (inserts_placed < insert_count || deletes_placed < delete_count))
        {
            if (inserts_placed <= deletes_placed && inserts_placed < insert_count)
            {
                ops[pos++] = OP_INSERT;
                inserts_placed++;
            }
            else if (deletes_placed < delete_count)
            {
                ops[pos++] = OP_DELETE;
                deletes_placed++;
            }
        }
    }

    // Fill any remaining slots with reads
    for (size_t i = 0; i < total; i++)
    {
        if (pos >= total)
            break;
        if (reads_placed < read_count)
        {
            // Find next empty slot
            while (pos < total && ops[pos] != 0)
                pos++;
            if (pos < total)
            {
                ops[pos] = OP_READ;
                reads_placed++;
            }
        }
    }
}

BenchmarkResult run_benchmark(DataStructure *ds, OperationMix *mix)
{
    BenchmarkResult result = {0};

    // Generate operation sequence with minimum spacing
    OperationType *operations = calloc(mix->total_operations, sizeof(OperationType));
    generate_operations_minimum_spacing(operations, mix);

    size_t current_index = 0;
    uint64_t checksum = 0;

    // Warm up to reduce measurement noise
    for (int i = 0; i < 1000; i++)
    {
        int val = ds->get(ds->data_structure, i % *ds->current_size);
        checksum += val;
    }

    double start_time = get_time();
    uint64_t start_cycles = get_cycles();

    for (size_t i = 0; i < mix->total_operations; i++)
    {
        switch (operations[i])
        {
        case OP_READ:
        {
            int value = ds->get(ds->data_structure, current_index);
            checksum += value; // Prevent optimization
            break;
        }
        case OP_WRITE:
        {
            // Use non-constant value to prevent optimization
            ds->set(ds->data_structure, current_index, (int)(i ^ checksum) & 0xFF);
            break;
        }
        case OP_INSERT:
        {
            ds->insert(ds->data_structure, current_index, (int)(i ^ checksum) & 0xFF);
            break;
        }
        case OP_DELETE:
        {
            ds->delete(ds->data_structure, current_index);
            break;
        }
        }

        // Linear traversal with wraparound
        if (*ds->current_size > 0)
        {
            current_index = (current_index + 1) % *ds->current_size;
        }
    }

    double end_time = get_time();
    uint64_t end_cycles = get_cycles();

    result.total_time = end_time - start_time;
    result.operations_done = mix->total_operations;
    result.ops_per_second = result.operations_done / result.total_time;
    result.checksum = checksum;
    if (end_cycles > start_cycles)
    {
        result.cycles_per_op = (end_cycles - start_cycles) / mix->total_operations;
    }

    free(operations);
    return result;
}

void print_benchmark_result(BenchmarkResult *result)
{
    printf("Benchmark Results:\n");
    printf("Total Time: %.6f seconds\n", result->total_time);
    printf("Operations Completed: %zu\n", result->operations_done);
    printf("Operations per Second: %.2f\n", result->ops_per_second);
    if (result->cycles_per_op > 0)
    {
        printf("Cycles per Operation: %llu\n", result->cycles_per_op); // Change %lu to %llu
    }
    printf("Checksum: %llu (prevents optimization)\n", result->checksum); // Change %lu to %llu
}
