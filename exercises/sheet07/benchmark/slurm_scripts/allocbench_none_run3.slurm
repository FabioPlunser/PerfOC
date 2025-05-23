#!/bin/bash
#SBATCH --job-name=allocbench_none_run3
#SBATCH --output=/gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/slurm_logs/allocbench_none_run3.slog
#SBATCH --error=/gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/slurm_logs/allocbench_none_run3.slog
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH --partition=lva

echo "--- Slurm Job Start ---"
date
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on: $(hostname)"
echo "CPUs per task: $SLURM_CPUS_PER_TASK"
echo "Working directory: $(pwd)"
echo "Allocator: none"
echo "Run number: 3"
echo "Metrics output file: /gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/job_metrics_output/metrics_none_run3.txt"
echo "Original Allscale source: /gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/allscale_api"
echo "LD_PRELOAD value: "
echo "--- Modules ---"
module purge
module load gcc/12.2.0-gcc-8.5.0-p4pe45v 
module load ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6
module load python/3.10.8-gcc-8.5.0-r5lf3ij  
module load llvm/15.0.4-python-3.10.8-gcc-8.5.0-bq44zh7
module list

echo "--- Environment ---"
# env # Can be very verbose, uncomment if needed for debugging
echo "--- Setup Local Benchmark Directory ---"
# Using a timestamp and PID for more uniqueness in /tmp
LOCAL_BENCH_DIR="/tmp/cb761223/none_3/allscale_api_code"
LOCAL_SRC_DIR="${LOCAL_BENCH_DIR}"
LOCAL_BUILD_DIR="${LOCAL_BENCH_DIR}/build"

trap 'echo "ERROR: Script interrupted. Cleaning up ${LOCAL_BENCH_DIR}"; cd /; rm -rf "${LOCAL_BENCH_DIR}"; exit 1' TERM INT


cd "${LOCAL_BENCH_DIR}"
mkdir -p "${LOCAL_BUILD_DIR}"
cd "${LOCAL_BUILD_DIR}"

echo "--- CMake Configuration ---"
cmake -DCMAKE_BUILD_TYPE=Release -G Ninja ../code
if [ $? -ne 0 ]; then echo "ERROR: CMake failed."; cd /; rm -rf "${LOCAL_BENCH_DIR}"; exit 1; fi

echo "--- Ninja Clean ---"
ninja clean
if [ $? -ne 0 ]; then echo "ERROR: ninja clean failed."; cd /; rm -rf "${LOCAL_BENCH_DIR}"; exit 1; fi

echo "--- Running Ninja Build (Benchmark) ---"
# /usr/bin/time -v writes to stderr. We redirect stderr to the metrics_output_file.
# stdout of ninja goes to a separate log in the build dir.
export LD_PRELOAD=""
echo "LD_PRELOAD is set to: '$LD_PRELOAD'"

# Check if LD_PRELOAD library exists if it's set
if [ -n "$LD_PRELOAD" ] && [ ! -f "$LD_PRELOAD" ]; then
    echo "ERROR: LD_PRELOAD library '$LD_PRELOAD' not found!"
    cd /
    rm -rf "${LOCAL_BENCH_DIR}"
    exit 1
fi

/usr/bin/time -v ninja -j16 > ninja_stdout.log 2> "/gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/job_metrics_output/metrics_none_run3.txt"
BUILD_EXIT_CODE=$?

echo "Ninja build exit code: $BUILD_EXIT_CODE"
if [ $BUILD_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Ninja build failed. See ninja_stdout.log in ${LOCAL_BUILD_DIR}"
    echo "Metrics file /gpfs/gpfs1/scratch/cb761223/exercises/sheet07/benchmark/job_metrics_output/metrics_none_run3.txt might contain partial /usr/bin/time output or error messages."
fi

echo "--- Cleaning Up /tmp ---"
cd / # Change out of the directory before removing it
rm -rf "${LOCAL_BENCH_DIR}"

echo "--- Slurm Job End ---"
date
exit $BUILD_EXIT_CODE
