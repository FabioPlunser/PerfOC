#!/bin/bash
#SBATCH --job-name=bench_094_run3
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --time=00:01:00
#SBATCH --output=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_094_run3.out
#SBATCH --error=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_094_run3.out

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
echo "Starting benchmark: bench_094_run3"
echo "Data Structure: list_rand"
echo "Elements: 10"
echo "Element Size: 8388608 bytes"
echo "Ins/Del Ratio: 0.5"
echo "Read/Write Ratio: 0.5"
echo "Estimated Memory: 168.0 MB"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v /scratch/cb761223/exercises/sheet09/src/benchmark \
    list_rand \
    10 \
    0.5 \
    0.5

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
