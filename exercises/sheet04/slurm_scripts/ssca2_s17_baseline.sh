#!/bin/bash

#SBATCH --partition=lva
#SBATCH --job-name=ssca2_s17_baseline
#SBATCH --output=/scratch/cb761223/exercises/sheet04/slurm_logs/ssca2_s17_baseline.log # Log path in logs_dir
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --exclusive

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on host: $(hostname)"
echo "Working directory: $(pwd)" # Submission directory
echo "Output log: /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/slurm_logs/ssca2_s17_baseline.log"
echo "Job started at: $(date)"
echo "--- Loading Modules ---"

# Load required modules
module load gcc/12.2.0-gcc-8.5.0-p4pe45v
module load cmake/3.24.3-gcc-8.5.0-svdlhox
module load ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6
module load python/3.10.8-gcc-8.5.0-r5lf3ij
module list

echo "--- Environment ---"
env | sort

echo "--- Execution ---"
echo "Executable directory: /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/ssca2/build"
echo "Executing command: /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/ssca2/build/ssca2 17"

# Run the command from the directory where the executable resides
cd /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/ssca2/build
time (/gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/ssca2/build/ssca2 17) > /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/slurm_logs/ssca2_s17_baseline.txt

exit_code=$?
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

exit $exit_code
