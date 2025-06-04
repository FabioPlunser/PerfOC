#!/bin/bash
#SBATCH --job-name=delannoy_memo_N15_rep3
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:60:00
#SBATCH --output=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_memo_N15_rep3.out
#SBATCH --error=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_memo_N15_rep3.out

echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on: $(hostname)"
echo "Start time: $(date)"
echo "Program: delannoy_memo"
echo "N: 15"
echo "Repetition: 3"
echo "Executable: /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_memo"
echo "----------------------------------------"

# The /usr/bin/time command provides detailed resource usage.
# -v flag for verbose output.
/usr/bin/time -v /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_memo 15

echo "----------------------------------------"
echo "End time: $(date)"
echo "Job completed."
