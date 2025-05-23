#!/bin/bash
#SBATCH --job-name=bench_036_run2
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --time=00:01:00
#SBATCH --output=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_036_run2.out
#SBATCH --error=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_036_run2.out

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
echo "Starting benchmark: bench_036_run2"
echo "Data Structure: list_seq"
echo "Elements: 10"
echo "Element Size: 8 bytes"
echo "Ins/Del Ratio: 0.0"
echo "Read/Write Ratio: 1.0"
echo "Estimated Memory: 0.0 MB"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v /scratch/cb761223/exercises/sheet09/src/benchmark \
    list_seq \
    10 \
    1.0 \
    0.0

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
