#!/usr/bin/env python3

import os
import subprocess
import stat
import time
from pathlib import Path
import re
import math

# --- Configuration ---
BASE_DIR = Path("/scratch/cb761223/perf-oriented-dev/larger_samples")
NPB_BT_SRC_DIR = BASE_DIR / "npb_bt"
SSCA2_SRC_DIR = BASE_DIR / "ssca2"

# Main output directory for this specific analysis
BASE_OUTPUT_DIR = Path("/scratch/cb761223/exercises/sheet04/perf") # Changed base dir
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Subdirectories for organization
SLURM_SCRIPTS_DIR = BASE_OUTPUT_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_OUTPUT_DIR / "slurm_logs"
PERF_OUTPUTS_DIR = BASE_OUTPUT_DIR / "perf_outputs" # New directory for perf results
SLURM_SCRIPTS_DIR.mkdir(exist_ok=True)
SLURM_LOGS_DIR.mkdir(exist_ok=True)
PERF_OUTPUTS_DIR.mkdir(exist_ok=True)


# Executable names (SSCA2 is fixed, NPB BT will be discovered)
SSCA2_EXE = "ssca2"
NPB_BT_PATTERN = "npb_bt_*" # Pattern to find NPB executables

# SSCA2 Scales to test
SSCA2_SCALES = [8, 17]

# Modules to load in Slurm jobs
MODULES = [
    "gcc/12.2.0-gcc-8.5.0-p4pe45v",
    "cmake/3.24.3-gcc-8.5.0-svdlhox",
    "ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6",
    "python/3.10.8-gcc-8.5.0-r5lf3ij",
  ]

# --- Perf Configuration ---
# Hardware cache events to measure
PERF_EVENTS = [
    "L1-dcache-load-misses",
    "L1-dcache-loads",
    "L1-dcache-prefetch-misses", 
    "L1-dcache-prefetches",      
    "L1-dcache-store-misses",
    "L1-dcache-stores",
    "L1-icache-load-misses",
    "L1-icache-loads",           
    "LLC-load-misses",
    "LLC-loads",
    "LLC-prefetch-misses",       
    "LLC-prefetches",            
    "LLC-store-misses",
    "LLC-stores",
    "branch-load-misses",
    "branch-loads",
    "dTLB-load-misses",
    "dTLB-loads",
    "dTLB-store-misses",
    "dTLB-stores",
    "iTLB-load-misses",
    "iTLB-loads",
    "node-load-misses",          
    "node-loads",                
    "node-prefetch-misses",      
    "node-prefetches",           
    "node-store-misses",         
    "node-stores",               
]

# Max number of hardware events per perf run (adjust based on hardware limits)
EVENTS_PER_GROUP = 4
num_groups = math.ceil(len(PERF_EVENTS) / EVENTS_PER_GROUP)
event_groups = [
    PERF_EVENTS[i * EVENTS_PER_GROUP:(i + 1) * EVENTS_PER_GROUP]
    for i in range(num_groups)
]

print(f"Dividing {len(PERF_EVENTS)} events into {num_groups} groups of up to {EVENTS_PER_GROUP}.")

def run_command(cmd, cwd=None, env=None, check=True):
    """Runs a command and prints output."""
    print(f"Running: {' '.join(cmd)} in {cwd or os.getcwd()}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env
    )
    # Limit output printing for potentially long build logs
    max_lines = 20
    stdout_lines = result.stdout.splitlines()
    stderr_lines = result.stderr.splitlines()

    if stdout_lines:
        print(f"STDOUT (last {max_lines} lines):\n" + "\n".join(stdout_lines[-max_lines:]))
        if len(stdout_lines) > max_lines: print("...")
    if stderr_lines:
        print(f"STDERR (last {max_lines} lines):\n" + "\n".join(stderr_lines[-max_lines:]))
        if len(stderr_lines) > max_lines: print("...")

    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        print(f"Full STDOUT:\n{result.stdout}") # Print full output on error
        print(f"Full STDERR:\n{result.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result

def build_program(src_dir: Path, build_dir: Path):
    """Builds a program using CMake and Ninja."""
    print(f"\n--- Building {src_dir.name} ---")
    build_dir.mkdir(exist_ok=True)
    try:
        cmake_cmd = [
            "cmake",
            str(src_dir.resolve()), # Use absolute path to source
            "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release", # Use Release for performance measurements
        ]
        cache_file = build_dir / "CMakeCache.txt"
        cmakelists_file = src_dir / "CMakeLists.txt"
        run_cmake = True
        if cache_file.exists():
             if cmakelists_file.exists():
                 if cache_file.stat().st_mtime >= cmakelists_file.stat().st_mtime:
                     print("CMake cache is up-to-date, skipping CMake execution.")
                     run_cmake = False
             else:
                 print(f"Warning: {cmakelists_file} not found, running CMake.")

        if run_cmake:
             print("Running CMake...")
             run_command(cmake_cmd, cwd=build_dir)
        else:
             print("Skipping CMake execution.")


        ninja_cmd = ["ninja"]
        print("Running Ninja...")
        result = run_command(ninja_cmd, cwd=build_dir, check=False)
        if result.returncode != 0:
             print(f"!!! Ninja build failed for {src_dir.name} with exit code {result.returncode}")
             raise RuntimeError(f"Ninja build failed for {src_dir.name}")
        print(f"--- Build potentially successful for {src_dir.name} (check output) ---")
    except Exception as e:
        print(f"!!! Build process failed for {src_dir.name}: {e}")
        raise

def generate_slurm_script(
    job_name: str,
    program_command: list[str], # The command to run the program itself
    scripts_dir: Path,
    logs_dir: Path,
    output_log_name: str,
    executable_dir: Path,
    perf_events: list[str] = None, # List of events for perf stat
    perf_output_dir: Path = None, # Directory for perf output file
    perf_output_filename: str = None # Specific name for perf output file
):
    """Generates a Slurm script file. Can optionally wrap command with perf."""
    slurm_script_path = scripts_dir / f"{job_name}.sh"
    output_log_path = logs_dir / output_log_name # Slurm log file

    abs_executable_dir = executable_dir.resolve()

    # Resolve program path within the program_command
    abs_program_command = []
    program_exe_path_str = None
    for i, item in enumerate(program_command):
        potential_path = Path(item)
        is_executable_in_cmd = False
        try:
            # Simplistic check: if it looks like a path within the build dir
            if str(potential_path.resolve()).startswith(str(abs_executable_dir)):
                 resolved_path = potential_path.resolve()
                 if resolved_path.is_file():
                     abs_program_command.append(str(resolved_path))
                     if i == 0: # Assume first element is the program
                         program_exe_path_str = str(resolved_path)
                     is_executable_in_cmd = True
        except OSError:
            pass # Ignore errors for non-path arguments

        if not is_executable_in_cmd:
            abs_program_command.append(item) # Keep args as is

    if not program_exe_path_str and abs_program_command:
         print(f"Warning: Could not definitively identify executable path in command: {' '.join(program_command)}")
         # Fallback: assume the first element is the command/executable
         program_exe_path_str = abs_program_command[0]


    # Construct the final command to be executed in Slurm
    if perf_events and perf_output_dir and perf_output_filename:
        # Running with perf stat
        if not perf_events:
             print(f"Warning: perf requested for {job_name} but no events specified. Running baseline.")
             final_command_list = abs_program_command
        else:
            abs_perf_output_path = (perf_output_dir / perf_output_filename).resolve()
            events_str = ",".join(perf_events)
            # Use -o for output file, -- to separate perf options from program
            final_command_list = [
                "perf", "stat",
                "-e", events_str,
                "-o", str(abs_perf_output_path),
                "--"
            ] + abs_program_command
            print(f"Perf output will be saved to: {abs_perf_output_path}")
    else:
        # Running baseline (no perf)
        final_command_list = abs_program_command

    final_command_str = ' '.join(final_command_list)

    script_content = f"""#!/bin/bash

#SBATCH --partition=lva
#SBATCH --job-name={job_name}
#SBATCH --output={output_log_path.resolve()} # Log path in logs_dir
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --exclusive
#SBATCH --time=01:00:00 # Set a reasonable time limit

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on host: $(hostname)"
echo "Working directory: $(pwd)" # Submission directory
echo "Output log: {output_log_path.resolve()}"
echo "Job started at: $(date)"
echo "--- Loading Modules ---"

# Load required modules
{chr(10).join([f"module load {mod}" for mod in MODULES])}
module list

echo "--- Environment ---"
env | sort

echo "--- Execution ---"
echo "Executable directory: {abs_executable_dir}"
echo "Executing command: {final_command_str}"

# Run the command from the directory where the executable resides
cd {abs_executable_dir}

# Use time utility to measure wall clock time of the (potentially perf-wrapped) command
# The output of 'time' goes to stderr, which Slurm redirects to the output log file.
# Perf output goes to the file specified by -o. Program stdout/stderr might be redirected
# depending on the program itself, or appear in the Slurm log if not redirected.
time ({final_command_str})

exit_code=$?
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

# Check if perf output file was created (if perf was used)
"""
    if perf_output_filename and perf_output_dir:
        abs_perf_output_path_str = str((perf_output_dir / perf_output_filename).resolve())
        script_content += f"""
if [ -f "{abs_perf_output_path_str}" ]; then
    echo "Perf output file generated: {abs_perf_output_path_str}"
    echo "--- Perf Output Preview (first/last 10 lines) ---"
    head -n 10 "{abs_perf_output_path_str}"
    echo "..."
    tail -n 10 "{abs_perf_output_path_str}"
    echo "--- End Perf Output Preview ---"
else
    echo "Warning: Expected perf output file not found: {abs_perf_output_path_str}"
fi
"""

    script_content += "\nexit $exit_code\n"

    with open(slurm_script_path, "w") as f:
        f.write(script_content)

    st = os.stat(slurm_script_path)
    os.chmod(slurm_script_path, st.st_mode | stat.S_IEXEC)

    print(f"Generated Slurm script: {slurm_script_path}")
    return slurm_script_path

def submit_slurm_job(script_path: Path):
    """Submits a Slurm script using sbatch."""
    sbatch_cmd = ["sbatch", str(script_path)]
    try:
        result = run_command(sbatch_cmd, check=True)
        job_id = result.stdout.strip().split()[-1]
        print(f"Successfully submitted job {job_id} from {script_path.name}")
        return job_id
    except Exception as e:
        print(f"!!! Failed to submit job from {script_path.name}: {e}")
        return None

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting Performance Counter Analysis Script")
    print(f"Base output directory: {BASE_OUTPUT_DIR}")
    print(f"Slurm scripts in:    {SLURM_SCRIPTS_DIR}")
    print(f"Slurm logs in:       {SLURM_LOGS_DIR}")
    print(f"Perf outputs in:     {PERF_OUTPUTS_DIR}")


    # 0. Check for sbatch and perf commands
    try:
        run_command(["which", "sbatch"], check=True)
        print("DEBUG: 'sbatch' command found.")
    except Exception:
        print("ERROR: 'sbatch' command not found. Cannot submit jobs.")
        print("Ensure you are on a system with Slurm or load the Slurm module.")
        exit(1)
    try:
        run_command(["which", "perf"], check=True)
        print("DEBUG: 'perf' command found.")
    except Exception:
        print("ERROR: 'perf' command not found. Cannot run performance analysis.")
        print("Ensure 'perf' (linux-tools) is installed or load the appropriate module.")
        exit(1)


    # 1. Build Programs
    npb_bt_build_dir = NPB_BT_SRC_DIR / "build" # Use separate build dir if desired
    ssca2_build_dir = SSCA2_SRC_DIR / "build"   # Use separate build dir if desired
    try:
        print("\n=== Attempting to build NPB BT ===")
        build_program(NPB_BT_SRC_DIR, npb_bt_build_dir)
        print("\n=== Attempting to build SSCA2 ===")
        build_program(SSCA2_SRC_DIR, ssca2_build_dir)
    except Exception as e:
        print(f"A build failed. Please check logs above. Exiting. Error: {e}")
        exit(1)

    # Find NPB BT executables AFTER build attempt
    print(f"\n--- Searching for NPB BT executables in: {npb_bt_build_dir} ---")
    npb_bt_executables = [
      p for p in npb_bt_build_dir.glob(NPB_BT_PATTERN)
      if p.is_file() and os.access(p, os.X_OK) and "txt" not in p.name
    ]
    if npb_bt_executables:
        npb_bt_executables = [p for p in npb_bt_executables if p.is_file() and os.access(p, os.X_OK)]
        print(f"Found NPB BT executables: {[p.name for p in npb_bt_executables]}")
    if not npb_bt_executables:
        print(f"WARNING: No executable NPB BT files found matching '{NPB_BT_PATTERN}' in {npb_bt_build_dir}. Skipping NPB BT.")

    ssca2_exe_path = ssca2_build_dir / SSCA2_EXE
    ssca2_exists = ssca2_exe_path.exists() and ssca2_exe_path.is_file() and os.access(ssca2_exe_path, os.X_OK)
    if not ssca2_exists:
        print(f"ERROR: Expected SSCA2 executable not found or not executable: {ssca2_exe_path}. Skipping SSCA2.")


    # 2. Generate and Submit Slurm Scripts
    should_submit = False
    submit_jobs = input("\nSubmit generated Slurm jobs? (y/n): ").lower()
    if submit_jobs == 'y':
        should_submit = True

    submitted_jobs = {}

    print("\n--- Generating and Submitting Slurm Jobs ---")

    # --- NPB BT Runs ---
    if npb_bt_executables:
        npb_regex = re.compile(r"npb_bt_([A-Za-z0-9_.-]+)")

        for npb_bt_exe_path in npb_bt_executables:
            match = npb_regex.match(npb_bt_exe_path.name)
            if not match:
                print(f"Warning: Could not extract identifier from {npb_bt_exe_path.name}, skipping.")
                continue

            npb_identifier = match.group(1)
            print(f"\n--- Processing NPB BT Identifier '{npb_identifier}' ---")

            # Baseline Run
            job_name_npb_base = f"npb_bt_{npb_identifier}_baseline"
            cmd_npb_base = [str(npb_bt_exe_path)]
            script_path_npb_base = generate_slurm_script(
                job_name=job_name_npb_base,
                program_command=cmd_npb_base,
                scripts_dir=SLURM_SCRIPTS_DIR,
                logs_dir=SLURM_LOGS_DIR,
                output_log_name=f"{job_name_npb_base}.log",
                executable_dir=npb_bt_build_dir,
                # No perf args for baseline
            )
            if should_submit:
                job_id = submit_slurm_job(script_path_npb_base)
                if job_id: submitted_jobs[job_name_npb_base] = job_id
                time.sleep(0.2) # Small delay between submissions
            else:
                print(f"Generated Slurm script (not submitted): {script_path_npb_base}")

            # Perf Runs (one per event group)
            for i, group in enumerate(event_groups):
                group_num = i + 1
                job_name_npb_perf = f"npb_bt_{npb_identifier}_perf_grp{group_num}"
                perf_output_filename = f"perf.out.{job_name_npb_perf}"
                cmd_npb_perf = [str(npb_bt_exe_path)] # Base command for the program

                script_path_npb_perf = generate_slurm_script(
                    job_name=job_name_npb_perf,
                    program_command=cmd_npb_perf,
                    scripts_dir=SLURM_SCRIPTS_DIR,
                    logs_dir=SLURM_LOGS_DIR,
                    output_log_name=f"{job_name_npb_perf}.log",
                    executable_dir=npb_bt_build_dir,
                    perf_events=group,
                    perf_output_dir=PERF_OUTPUTS_DIR,
                    perf_output_filename=perf_output_filename
                )
                if should_submit:
                    job_id = submit_slurm_job(script_path_npb_perf)
                    if job_id: submitted_jobs[job_name_npb_perf] = job_id
                    time.sleep(0.2) # Small delay
                else:
                    print(f"Generated Slurm script (not submitted): {script_path_npb_perf}")

    # --- SSCA2 Runs ---
    if ssca2_exists:
        print(f"\n--- Processing SSCA2 ---")
        for scale in SSCA2_SCALES:
            print(f"--- SSCA2 Scale {scale} ---")

            # Baseline Run
            job_name_ssca2_base = f"ssca2_s{scale}_baseline"
            cmd_ssca2_base = [str(ssca2_exe_path), str(scale)]
            script_path_ssca2_base = generate_slurm_script(
                job_name=job_name_ssca2_base,
                program_command=cmd_ssca2_base,
                scripts_dir=SLURM_SCRIPTS_DIR,
                logs_dir=SLURM_LOGS_DIR,
                output_log_name=f"{job_name_ssca2_base}.log",
                executable_dir=ssca2_build_dir,
            )
            if should_submit:
                job_id = submit_slurm_job(script_path_ssca2_base)
                if job_id: submitted_jobs[job_name_ssca2_base] = job_id
                time.sleep(0.2)
            else:
                print(f"Generated Slurm script (not submitted): {script_path_ssca2_base}")

            # Perf Runs (one per event group)
            for i, group in enumerate(event_groups):
                group_num = i + 1
                job_name_ssca2_perf = f"ssca2_s{scale}_perf_grp{group_num}"
                perf_output_filename = f"perf.out.{job_name_ssca2_perf}"
                cmd_ssca2_perf = [str(ssca2_exe_path), str(scale)] # Base command

                script_path_ssca2_perf = generate_slurm_script(
                    job_name=job_name_ssca2_perf,
                    program_command=cmd_ssca2_perf,
                    scripts_dir=SLURM_SCRIPTS_DIR,
                    logs_dir=SLURM_LOGS_DIR,
                    output_log_name=f"{job_name_ssca2_perf}.log",
                    executable_dir=ssca2_build_dir,
                    perf_events=group,
                    perf_output_dir=PERF_OUTPUTS_DIR,
                    perf_output_filename=perf_output_filename
                )
                if should_submit:
                    job_id = submit_slurm_job(script_path_ssca2_perf)
                    if job_id: submitted_jobs[job_name_ssca2_perf] = job_id
                    time.sleep(0.2)
                else:
                    print(f"Generated Slurm script (not submitted): {script_path_ssca2_perf}")
    else:
        print("\nSkipping SSCA2 job generation because executable was not found or not executable.")


    # 3. Print Instructions
    print("\n--- Setup and Submission Complete ---")
    print(f"Build artifacts should be in {npb_bt_build_dir} and {ssca2_build_dir}")
    print(f"Slurm scripts generated in: {SLURM_SCRIPTS_DIR}")
    print(f"Slurm logs will appear in:  {SLURM_LOGS_DIR}")
    print(f"Perf output files will appear in: {PERF_OUTPUTS_DIR}")

    print("\nSubmitted Slurm jobs:")
    if submitted_jobs:
        for name in sorted(submitted_jobs.keys()):
            print(f"  Job Name: {name}, Job ID: {submitted_jobs[name]}")
    else:
        print("  No jobs were submitted (or submission was skipped).")

    print(f"\nMonitor job status using: squeue -u $USER")
    print(f"Check Slurm output logs (*.log) in '{SLURM_LOGS_DIR}' for errors and timing.")
    print(f"Check perf output files (perf.out.*) in '{PERF_OUTPUTS_DIR}' once jobs complete.")

    print("\n--- Analysis Steps After Jobs Complete ---")
    print("1. Check Baseline Runtimes:")
    print(f"   - Examine the *.log files in {SLURM_LOGS_DIR} for the 'baseline' jobs.")
    print(f"   - Look for the 'real' time reported by the 'time' command near the end of the log.")
    print(f"   - Example: grep 'real' {SLURM_LOGS_DIR}/*baseline.log")

    print("\n2. Check Perf Runtimes & Overhead:")
    print(f"   - Examine the *.log files in {SLURM_LOGS_DIR} for the 'perf_grp*' jobs.")
    print(f"   - Look for the 'real' time reported by the 'time' command.")
    print(f"   - Compare this 'real' time to the baseline 'real' time for the same program/scale.")
    print(f"   - The difference indicates the overhead introduced by running 'perf stat'.")
    print(f"   - Example: grep 'real' {SLURM_LOGS_DIR}/*perf_grp*.log")

    print("\n3. Analyze Performance Counters:")
    print(f"   - Examine the 'perf.out.*' files in {PERF_OUTPUTS_DIR}.")
    print(f"   - Each file contains the counts for one group of events for a specific run.")
    print(f"   - Example: cat {PERF_OUTPUTS_DIR}/perf.out.npb_bt_A_perf_grp1")
    print(f"   - Collect the counts for all events for each program configuration (NPB identifier or SSCA2 scale) by looking across the group files.")

    print("\n4. Calculate Relative Metrics:")
    print("   - Use the collected counts to calculate meaningful ratios (miss rates, etc.). Examples:")
    print("     - L1 D-Cache Load Miss Rate = L1-dcache-load-misses / L1-dcache-loads")
    print("     - L1 I-Cache Load Miss Rate = L1-icache-load-misses / L1-icache-loads (if L1-icache-loads available)")
    print("     - LLC Load Miss Rate        = LLC-load-misses / LLC-loads")
    print("     - dTLB Load Miss Rate       = dTLB-load-misses / dTLB-loads")
    print("     - Branch Misprediction Rate (approx) = branch-load-misses / branch-loads (Note: 'branch-misses' is often preferred if available)")
    print("   - Be aware that some counters might report '<not supported>' or 0 if the event is not available or didn't occur.")

    print("\n5. Compare Programs:")
    print("   - Compare the calculated relative metrics (miss rates, etc.) between NPB BT (for a given class, e.g., W or A) and SSCA2 (for a given scale).")
    print("   - Discuss differences in cache behavior, TLB behavior, etc., based on these metrics.")
    print("   - Relate these differences to the likely workload characteristics of each benchmark (e.g., memory access patterns, instruction footprint).")

    print("\n6. Assess Perturbation:")
    print("   - Based on the comparison in step 2 (baseline vs. perf runtimes), comment on how significant the execution time perturbation caused by `perf stat` was for these benchmarks and event groups.")
    print("   - Did the overhead seem constant, or did it vary between programs or scales?")

    print("\nScript finished.")
