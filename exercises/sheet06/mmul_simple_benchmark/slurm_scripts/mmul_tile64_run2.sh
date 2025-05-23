#!/bin/bash
#SBATCH --partition=lva
#SBATCH --job-name=mmul_tile64_run2
#SBATCH --output=/gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/slurm_logs/mmul_tile64_run2.log
#SBATCH --error=/gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/slurm_logs/mmul_tile64_run2.log # Combine stdout/stderr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:45:00
#SBATCH --exclusive


echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Tile Size: 64"
echo "Run Index: 2/5"
echo "Executable: /gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/build/mmul_tiled_exec"
echo "Log File: /gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/slurm_logs/mmul_tile64_run2.log"
echo "Job started on $(hostname) at $(date)"

echo "--- Execution ---"
# No need to cd if using absolute path for executable

echo "Running command: time -p /gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/build/mmul_tiled_exec 64"
echo "-------------------- Program Output Start --------------------"

time -p /gpfs/gpfs1/scratch/cb761223/exercises/sheet06/mmul_simple_benchmark/build/mmul_tiled_exec 64

exit_code=$?
echo "-------------------- Program Output End ----------------------"
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

exit $exit_code
