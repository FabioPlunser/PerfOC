#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path

# Set up directories
SCRIPT_DIR = Path("/scratch/cb761223/perf-oriented-dev/small_samples/")
BUILD_DIR = SCRIPT_DIR / "build"
OUTPUT_DIR = SCRIPT_DIR / "benchmark_results"
SLURM_DIR = SCRIPT_DIR / "slurm_scripts"

# Create directories if they don't exist
BUILD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
SLURM_DIR.mkdir(exist_ok=True)

# Build the programs if not already built
def build_programs():
    print("Building programs...")
    os.chdir(BUILD_DIR)
    
    # Run CMake if not already configured
    if not (BUILD_DIR / "build.ninja").exists():
        subprocess.run(["cmake", "..", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"], check=True)
    
    # Build all programs
    subprocess.run(["ninja"], check=True)
    
    os.chdir(SCRIPT_DIR)
    print("Build complete.")

CMD = '/usr/bin/time -v -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB"'
# Define benchmark configurations
BENCHMARKS = [
    {
        "name": "delannoy",
        "command": f"./delannoy 14",
        "description": "Delannoy number calculation with N=14"
    },
    {
        "name": "file_generator",
        "command": f"./filegen 10 200 1024 102400 1234",
        "description": "File generator with 10 dirs, 200 files/dir, 1KB-100KB file sizes"
    },
    {
        "name": "find_largest_file",
        "command": f"./filesearch",
        "description": "Find largest file in current directory"
    },
    {
        "name": "matrix_mult",
        "command": f"./nmul",
        "description": "Matrix multiplication with default size S=1000"
    },
    {
        "name": "nbody",
        "command": f"./nbody",
        "description": "N-body simulation with default N=1000, M=100, L=1000"
    },
    {
        "name": "qap",
        "command": f"./qap problems/chr12a.dat",
        "description": "QAP solver with chr12a problem"
    }
]

# Create SLURM job scripts and submit them
def create_and_submit_jobs():
    for benchmark in BENCHMARKS:
        name = benchmark["name"]
        command = benchmark["command"]
        description = benchmark["description"]
        
        # Create SLURM script
        slurm_script = SLURM_DIR / f"{name}_job.sh"
        with open(slurm_script, 'w') as f:
            f.write(f"""#!/bin/bash
# Execute job in the partition "lva" unless you have special requirements.
#SBATCH --partition=lva
# Name your job to be able to identify it later
#SBATCH --job-name={name}_benchmark
# Redirect output stream to this file
#SBATCH --output={OUTPUT_DIR}/{name}_output.txt
# Maximum number of tasks (=processes) to start in total
#SBATCH --ntasks=1
# Maximum number of tasks (=processes) to start per node
#SBATCH --ntasks-per-node=1
# Enforce exclusive node allocation, do not share with other jobs
#SBATCH --exclusive

# Print job information
echo "Running benchmark: {name}"
echo "Description: {description}"
echo "Command: {command}"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "-------------------------------------"

# Change to build directory
cd {BUILD_DIR}

# Run the benchmark with time measurement
/usr/bin/time -v {command}

echo "-------------------------------------"
echo "Benchmark completed at $(date)"
""")
        
        # Make script executable
        os.chmod(slurm_script, 0o755)
        
        # Submit job
        print(f"Submitting job for {name}...")
        subprocess.run(["sbatch", str(slurm_script)], check=True)
        print(f"Job submitted for {name}")

def main():
    # Build the programs
    build_programs()
    
    # Create and submit SLURM jobs
    create_and_submit_jobs()
    
    print("\nAll benchmark jobs have been submitted to SLURM.")
    print(f"Results will be saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
