#!/bin/bash
#SBATCH --partition=lva
#SBATCH --job-name=qap_O2_plus_fpredictive_commoning_run3
#SBATCH --output=/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/qap_O2_plus_fpredictive_commoning_run3.log
#SBATCH --error=/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/qap_O2_plus_fpredictive_commoning_run3.log
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --exclusive

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Run Index: 3/5"
echo "Program: qap"
echo "Flags ID: O2_plus_fpredictive_commoning"
echo "Build Dir: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/qap/-O2_-fpredictive-commoning"
echo "Log File: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/qap_O2_plus_fpredictive_commoning_run3.log"
echo "Job started at: $(date)"

echo "--- Loading Modules ---"
module purge
module load gcc/12.2.0-gcc-8.5.0-p4pe45v
module load cmake/3.24.3-gcc-8.5.0-svdlhox
module load ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6
echo "Loaded modules:"
module list

echo "--- Execution ---"
echo "Changing directory to: /gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/qap/-O2_-fpredictive-commoning"
cd "/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/build/qap/-O2_-fpredictive-commoning" || exit 1

echo "Running command: time -p ./qap /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/small_samples/qap/problems/chr15c.dat"
echo "-------------------- Program Output Start --------------------"

time -p ./qap /gpfs/gpfs1/scratch/cb761223/perf-oriented-dev/small_samples/qap/problems/chr15c.dat

exit_code=$?
echo "-------------------- Program Output End ----------------------"
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

# Basic check for timing info
if grep -q "real" "/gpfs/gpfs1/scratch/cb761223/exercises/sheet05/benchmark/benchmark_output/slurm_logs/qap_O2_plus_fpredictive_commoning_run3.log"; then
    echo "Timing information should be present in the log."
else
    echo "WARNING: Timing information ('real') might be missing from the log."
fi

exit $exit_code
