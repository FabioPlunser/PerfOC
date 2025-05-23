#!/bin/bash
#SBATCH --job-name=bench_082_run2
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --time=00:01:00
#SBATCH --output=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_082_run2.out
#SBATCH --error=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_082_run2.out

# Load modules if needed
# module load gcc/11.2.0

# Change to benchmark directory
cd /scratch/cb761223/exercises/sheet09

# Ensure benchmark executable exists
if [ ! -f "/scratch/cb761223/exercises/sheet09/src/benchmark" ]; then
    echo "ERROR: Benchmark executable not found at /scratch/cb761223/exercises/sheet09/src/benchmark"
    exit 1
fi

# Run benchmark with timing
echo "Starting benchmark: bench_082_run2"
echo "Data Structure: list_rand"
echo "Elements: 100000"
echo "Element Size: 512 bytes"
echo "Ins/Del Ratio: 0.01"
echo "Read/Write Ratio: 0.99"
echo "Estimated Memory: 104.1 MB"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v /scratch/cb761223/exercises/sheet09/src/benchmark \
    list_rand \
    100000 \
    0.99 \
    0.01

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
