#!/bin/bash
#SBATCH --job-name=delannoy_tab_N22_rep4
#SBATCH --partition=lva
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:60:00
#SBATCH --output=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_tab_N22_rep4.out
#SBATCH --error=/scratch/cb761223/sheet11/benchmark/slurm_logs/delannoy_tab_N22_rep4.out

echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on: $(hostname)"
echo "Start time: $(date)"
echo "Program: delannoy_tab"
echo "N: 22"
echo "Repetition: 4"
echo "Executable: /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_tab"
echo "----------------------------------------"

# The /usr/bin/time command provides detailed resource usage.
# -v flag for verbose output.
/usr/bin/time -v /gpfs/gpfs1/scratch/cb761223/sheet11/benchmark/bin/delannoy_tab 22

echo "----------------------------------------"
echo "End time: $(date)"
echo "Job completed."
