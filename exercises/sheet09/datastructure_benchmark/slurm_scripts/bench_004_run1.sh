#!/bin/bash
#SBATCH --job-name=bench_004_run1
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --time=00:01:00
#SBATCH --output=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_004_run1.out
#SBATCH --error=/scratch/cb761223/exercises/sheet09/datastructure_benchmark/slurm_logs/bench_004_run1.out

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
echo "Starting benchmark: bench_004_run1"
echo "Data Structure: array"
echo "Elements: 1000"
echo "Element Size: 512 bytes"
echo "Ins/Del Ratio: 0.0"
echo "Read/Write Ratio: 1.0"
echo "Estimated Memory: 1.0 MB"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v /scratch/cb761223/exercises/sheet09/src/benchmark \
    array \
    1000 \
    1.0 \
    0.0

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
