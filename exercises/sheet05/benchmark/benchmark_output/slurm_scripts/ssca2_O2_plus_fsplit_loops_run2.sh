#!/bin/bash
#SBATCH --partition=lva
#SBATCH --job-name=ssca2_O2_plus_fsplit_loops_run2
#SBATCH --output=/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/ssca2_O2_plus_fsplit_loops_run2.log
#SBATCH --error=/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/ssca2_O2_plus_fsplit_loops_run2.log
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --exclusive

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Run Index: 2/5"
echo "Program: ssca2"
echo "Flags ID: O2_plus_fsplit_loops"
echo "Build Dir: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/ssca2/-O2_-fsplit-loops"
echo "Log File: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/ssca2_O2_plus_fsplit_loops_run2.log"
echo "Job started at: $(date)"

echo "--- Loading Modules ---"
module purge
module load gcc/12.2.0-gcc-8.5.0-p4pe45v
module load cmake/3.24.3-gcc-8.5.0-svdlhox
module load ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6
echo "Loaded modules:"
module list

echo "--- Execution ---"
echo "Changing directory to: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/ssca2/-O2_-fsplit-loops"
cd "/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/ssca2/-O2_-fsplit-loops" || exit 1

echo "Running command: time -p ./ssca2 10"
echo "-------------------- Program Output Start --------------------"

time -p ./ssca2 10

exit_code=$?
echo "-------------------- Program Output End ----------------------"
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

# Basic check for timing info
if grep -q "real" "/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/ssca2_O2_plus_fsplit_loops_run2.log"; then
    echo "Timing information should be present in the log."
else
    echo "WARNING: Timing information ('real') might be missing from the log."
fi

exit $exit_code
