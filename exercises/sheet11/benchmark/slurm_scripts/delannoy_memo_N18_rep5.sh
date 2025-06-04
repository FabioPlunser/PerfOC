#!/bin/bash
#SBATCH --job-name=delannoy_memo_N18_rep5
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:60:00
#SBATCH --output=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_memo_N18_rep5.out
#SBATCH --error=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_memo_N18_rep5.out

echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on: $(hostname)"
echo "Start time: $(date)"
echo "Program: delannoy_memo"
echo "N: 18"
echo "Repetition: 5"
echo "Executable: /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_memo"
echo "----------------------------------------"

# The /usr/bin/time command provides detailed resource usage.
# -v flag for verbose output.
/usr/bin/time -v /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_memo 18

echo "----------------------------------------"
echo "End time: $(date)"
echo "Job completed."
