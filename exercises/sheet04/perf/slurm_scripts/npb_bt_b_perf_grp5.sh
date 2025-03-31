#!/bin/bash

#SBATCH --partition=lva
#SBATCH --job-name=npb_bt_b_perf_grp5
#SBATCH --output=/gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/slurm_logs/npb_bt_b_perf_grp5.log # Log path in logs_dir
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --exclusive
#SBATCH --time=01:00:00 # Set a reasonable time limit

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on host: $(hostname)"
echo "Working directory: $(pwd)" # Submission directory
echo "Output log: /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/slurm_logs/npb_bt_b_perf_grp5.log"
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
echo "Executable directory: /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/npb_bt/build"
echo "Executing command: perf stat -e dTLB-load-misses,dTLB-loads,dTLB-store-misses,dTLB-stores -o /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5 -- /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/npb_bt/build/npb_bt_b"

# Run the command from the directory where the executable resides
cd /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/npb_bt/build

# Use time utility to measure wall clock time of the (potentially perf-wrapped) command
# The output of 'time' goes to stderr, which Slurm redirects to the output log file.
# Perf output goes to the file specified by -o. Program stdout/stderr might be redirected
# depending on the program itself, or appear in the Slurm log if not redirected.
time (perf stat -e dTLB-load-misses,dTLB-loads,dTLB-store-misses,dTLB-stores -o /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5 -- /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/larger_samples/npb_bt/build/npb_bt_b)

exit_code=$?
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

# Check if perf output file was created (if perf was used)

if [ -f "/gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5" ]; then
    echo "Perf output file generated: /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5"
    echo "--- Perf Output Preview (first/last 10 lines) ---"
    head -n 10 "/gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5"
    echo "..."
    tail -n 10 "/gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5"
    echo "--- End Perf Output Preview ---"
else
    echo "Warning: Expected perf output file not found: /gpfs/gpfs1/scratch/cb761223/exercises/sheet04/perf/perf_outputs/perf.out.npb_bt_b_perf_grp5"
fi

exit $exit_code
