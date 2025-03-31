#!/usr/bin/env python3

import os
import subprocess
import stat
import time
from pathlib import Path
import re # Import regular expressions for class extraction

# --- Configuration ---
BASE_DIR = Path("/scratch/cb761223/perf-oriented-dev/larger_samples")
NPB_BT_SRC_DIR = BASE_DIR / "npb_bt"
SSCA2_SRC_DIR = BASE_DIR / "ssca2"

# Main output directory
BASE_OUTPUT_DIR = Path("/scratch/cb761223/exercises/sheet04")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Subdirectories for organization
SLURM_SCRIPTS_DIR = BASE_OUTPUT_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_OUTPUT_DIR / "slurm_logs"
MASSIF_OUTPUTS_DIR = BASE_OUTPUT_DIR / "massif_outputs"
SLURM_SCRIPTS_DIR.mkdir(exist_ok=True)
SLURM_LOGS_DIR.mkdir(exist_ok=True)
MASSIF_OUTPUTS_DIR.mkdir(exist_ok=True)


# Executable names (SSCA2 is fixed, NPB BT will be discovered)
SSCA2_EXE = "ssca2"
# Corrected NPB pattern as requested
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

# --- Helper Functions ---

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
    if result.stdout:
        print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result

def build_program(src_dir: Path, build_dir: Path):
    """Builds a program using CMake and Ninja."""
    print(f"\n--- Building {src_dir.name} ---")
    build_dir.mkdir(exist_ok=True)
    try:
        cmake_cmd = [
            "cmake",
            str(src_dir), # Use absolute path to source
            "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
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
        # Run ninja command, check=False initially to see output even on failure
        result = run_command(ninja_cmd, cwd=build_dir, check=False)
        if result.returncode != 0:
             print(f"!!! Ninja build failed for {src_dir.name} with exit code {result.returncode}")
             # Optionally raise error or just warn
             raise RuntimeError(f"Ninja build failed for {src_dir.name}")
        print(f"--- Build potentially successful for {src_dir.name} (check output) ---")
    except Exception as e:
        print(f"!!! Build process failed for {src_dir.name}: {e}")
        raise

def generate_slurm_script(
    job_name: str,
    command: list[str],
    scripts_dir: Path, # Changed from log_dir
    logs_dir: Path,    # Added
    massif_dir: Path,  # Added
    output_log_name: str,
    executable_dir: Path,
    massif_output_filename: str = None # Optional: specific name for massif file
):
    """Generates a Slurm script file in scripts_dir, logs to logs_dir."""
    slurm_script_path = scripts_dir / f"{job_name}.sh"
    output_log_path = logs_dir / output_log_name # Log file goes to logs_dir

    abs_executable_dir = executable_dir.resolve()
    abs_command = []
    massif_out_arg = None

    for item in command:
        # Handle --massif-out-file separately to place it in massif_dir
        if item.startswith("--massif-out-file="):
            prefix, _ = item.split("=", 1)
            if not massif_output_filename:
                 # Default name if not provided (should be provided for massif runs)
                 massif_output_filename = f"massif.out.{job_name}"
            abs_massif_path = (massif_dir / massif_output_filename).resolve()
            massif_out_arg = f"{prefix}={abs_massif_path}"
            continue # Skip adding the original massif arg to abs_command

        # Resolve executable path if it's part of the command
        potential_path = Path(item)
        is_executable_in_cmd = False
        try:
            # Check if item resolves to a file (could be relative or absolute)
            if potential_path.is_file():
                 # Check if it's the main executable we intend to run
                 # This assumes the executable is the first file path in the command
                 if str(potential_path.resolve()).startswith(str(abs_executable_dir)):
                     is_executable_in_cmd = True
        except OSError as e:
             print(f"Warning: Error checking path {item}: {e}")

        if is_executable_in_cmd:
             abs_command.append(str(potential_path.resolve()))
        else:
             # Keep non-file arguments (like 'valgrind', '--tool=massif', scale) as is
             abs_command.append(item)

    # Reconstruct the final command, adding the modified massif path if needed
    final_command = list(abs_command) # Make a copy
    if massif_out_arg:
        # Try to insert the massif arg after '--tool=massif' or after 'valgrind'
        try:
            idx = final_command.index('--tool=massif')
            final_command.insert(idx + 1, massif_out_arg)
        except ValueError:
            try:
                 idx = final_command.index('valgrind')
                 final_command.insert(idx + 1, massif_out_arg)
            except ValueError:
                 # Fallback: append if valgrind/tool not found (unlikely)
                 final_command.append(massif_out_arg)


    script_content = f"""#!/bin/bash

#SBATCH --partition=lva
#SBATCH --job-name={job_name}
#SBATCH --output={output_log_path} # Log path in logs_dir
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --exclusive

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
echo "Executing command: {' '.join(final_command)}"

# Run the command from the directory where the executable resides
cd {abs_executable_dir}
time ({' '.join(final_command)}) > {str(output_log_path.resolve()).replace(".log", ".txt")}

exit_code=$?
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

exit $exit_code
"""
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
    print("Starting Memory Analysis Script")
    print(f"Base output directory: {BASE_OUTPUT_DIR}")
    print(f"Slurm scripts in:    {SLURM_SCRIPTS_DIR}")
    print(f"Slurm logs in:       {SLURM_LOGS_DIR}")
    print(f"Massif outputs in:   {MASSIF_OUTPUTS_DIR}")


    # 0. Check for sbatch command
    try:
        run_command(["which", "sbatch"], check=False)
        print("DEBUG: 'sbatch' command found.")
    except Exception:
        print("ERROR: 'sbatch' command not found. Cannot submit jobs.")
        print("Ensure you are on a system with Slurm or load the Slurm module.")
        exit(1)


    # 1. Build Programs
    npb_bt_build_dir = NPB_BT_SRC_DIR / "build"
    ssca2_build_dir = SSCA2_SRC_DIR / "build"
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
    # Use the corrected pattern
    npb_bt_executables = [
      p for p in npb_bt_build_dir.glob(NPB_BT_PATTERN)
      if p.is_file() and os.access(p, os.X_OK) and "txt" not in p.name
    ] 
    print(f"DEBUG: Files found by glob('{NPB_BT_PATTERN}'): {[p.name for p in npb_bt_executables]}")

    if not npb_bt_executables:
        print(f"WARNING: No NPB BT executables found matching '{NPB_BT_PATTERN}' in {npb_bt_build_dir}")
        print("         Please check the build output above to ensure compilation succeeded")
        print(f"         and that executables like '{NPB_BT_PATTERN}' exist in that directory.")
        print("Skipping NPB BT job generation.")
    else:
        # Filter out potential non-executable files if glob is too broad
        npb_bt_executables = [p for p in npb_bt_executables if p.is_file() and os.access(p, os.X_OK)]
        print(f"Found NPB BT executables (and executable): {[p.name for p in npb_bt_executables]}")
        if not npb_bt_executables:
             print("WARNING: No *executable* files matching pattern found. Skipping NPB BT.")


    ssca2_exe_path = ssca2_build_dir / SSCA2_EXE
    if not ssca2_exe_path.exists() or not ssca2_exe_path.is_file() or not os.access(ssca2_exe_path, os.X_OK):
        print(f"ERROR: Expected SSCA2 executable not found or not executable: {ssca2_exe_path}")
        # Decide whether to exit or continue
        # exit(1)


    # 2. Generate and Submit Slurm Scripts
    should_submit = False
    submit_jobs =  input("\nSubmit generated Slurm jobs? (y/n): ").lower()
    if submit_jobs == 'y': 
      should_submit = True 
      
    submitted_jobs = {}

    print("\n--- Generating and Submitting Slurm Jobs ---")

    # --- NPB BT Runs (Loop over discovered executables) ---
    if npb_bt_executables:
        # Corrected regex for "npb_bt_*" pattern
        npb_regex = re.compile(r"npb_bt_([A-Za-z0-9_.-]+)") # Capture identifier after npb_bt_

        for npb_bt_exe_path in npb_bt_executables:
            print(f"\nDEBUG: Processing NPB executable path: {npb_bt_exe_path}")
            print(f"DEBUG: Processing filename: {npb_bt_exe_path.name}")

            match = npb_regex.match(npb_bt_exe_path.name)
            print(f"DEBUG: Regex match result for identifier: {match}")

            if not match:
                print(f"Warning: Could not extract identifier from {npb_bt_exe_path.name} using regex '{npb_regex.pattern}', skipping this file.")
                continue

            npb_identifier = match.group(1) # Get the matched identifier (e.g., 'A', 'B', 'C', 'S', 'W')
            print(f"--- Processing NPB BT Identifier '{npb_identifier}' ---")

            # Baseline
            job_name_npb_base = f"npb_bt_{npb_identifier}_baseline"
            cmd_npb_base = [str(npb_bt_exe_path)]
            script_path_npb_base = generate_slurm_script(
                job_name=job_name_npb_base,
                command=cmd_npb_base,
                scripts_dir=SLURM_SCRIPTS_DIR, # Use scripts subdir
                logs_dir=SLURM_LOGS_DIR,       # Use logs subdir
                massif_dir=MASSIF_OUTPUTS_DIR, # Pass massif dir (though not used here)
                output_log_name=f"{job_name_npb_base}.log",
                executable_dir=npb_bt_build_dir,
            )
            if should_submit: 
              job_id = submit_slurm_job(script_path_npb_base)
              if job_id: submitted_jobs[job_name_npb_base] = job_id
              time.sleep(0.5)
            else:
              print(f"Slurm job {script_path_npb_base} not submitted")

            # Massif
            job_name_npb_massif = f"npb_bt_{npb_identifier}_massif"
            massif_output_filename = f"massif.out.{job_name_npb_massif}" # Specific name
            # Command for valgrind - pass placeholder for massif file path
            cmd_npb_massif = [
                "valgrind",
                "--tool=massif",
                "--massif-out-file=PLACEHOLDER", # Placeholder handled by generate_slurm_script
                str(npb_bt_exe_path),
            ]
            script_path_npb_massif = generate_slurm_script(
                job_name=job_name_npb_massif,
                command=cmd_npb_massif,
                scripts_dir=SLURM_SCRIPTS_DIR, # Use scripts subdir
                logs_dir=SLURM_LOGS_DIR,       # Use logs subdir
                massif_dir=MASSIF_OUTPUTS_DIR, # Use massif subdir
                output_log_name=f"{job_name_npb_massif}.log",
                executable_dir=npb_bt_build_dir,
                massif_output_filename=massif_output_filename # Provide specific name
            )
            if should_submit: 
              job_id = submit_slurm_job(script_path_npb_massif)
              if job_id: submitted_jobs[job_name_npb_massif] = job_id
              time.sleep(0.5)
            else:
              print(f"Slurm job {script_path_npb_massif}")


    # --- SSCA2 Runs ---
    if ssca2_exe_path.exists() and os.access(ssca2_exe_path, os.X_OK):
        print(f"\n--- Processing SSCA2 ---")
        for scale in SSCA2_SCALES:
            print(f"--- SSCA2 Scale {scale} ---")
            # Baseline
            job_name_ssca2_base = f"ssca2_s{scale}_baseline"
            cmd_ssca2_base = [str(ssca2_exe_path), str(scale)]
            script_path_ssca2_base = generate_slurm_script(
                job_name=job_name_ssca2_base,
                command=cmd_ssca2_base,
                scripts_dir=SLURM_SCRIPTS_DIR,
                logs_dir=SLURM_LOGS_DIR,
                massif_dir=MASSIF_OUTPUTS_DIR,
                output_log_name=f"{job_name_ssca2_base}.log",
                executable_dir=ssca2_build_dir,
            )
            if should_submit:
              job_id = submit_slurm_job(script_path_ssca2_base)
              if job_id: submitted_jobs[job_name_ssca2_base] = job_id
              time.sleep(0.5)
            else:
              print(f"Slurm job {script_path_ssca2_base} not submitted")

            # Massif
            job_name_ssca2_massif = f"ssca2_s{scale}_massif"
            massif_output_filename = f"massif.out.{job_name_ssca2_massif}"
            cmd_ssca2_massif = [
                "valgrind",
                "--tool=massif",
                "--massif-out-file=PLACEHOLDER", # Placeholder
                str(ssca2_exe_path),
                str(scale),
            ]
            script_path_ssca2_massif = generate_slurm_script(
                job_name=job_name_ssca2_massif,
                command=cmd_ssca2_massif,
                scripts_dir=SLURM_SCRIPTS_DIR,
                logs_dir=SLURM_LOGS_DIR,
                massif_dir=MASSIF_OUTPUTS_DIR,
                output_log_name=f"{job_name_ssca2_massif}.log",
                executable_dir=ssca2_build_dir,
                massif_output_filename=massif_output_filename
            )
            if should_submit:
              job_id = submit_slurm_job(script_path_ssca2_massif)
              if job_id: submitted_jobs[job_name_ssca2_massif] = job_id
              time.sleep(0.5)
            else:
              print(f"Slurm job {script_path_ssca2_massif} not submitted")
    else:
        print("\nSkipping SSCA2 job generation because executable was not found or not executable.")


    # 3. Print Instructions
    print("\n--- Setup and Submission Complete ---")
    print(f"Build artifacts should be in {npb_bt_build_dir} and {ssca2_build_dir}")
    print(f"Slurm scripts generated in: {SLURM_SCRIPTS_DIR}")
    print(f"Slurm logs will appear in:  {SLURM_LOGS_DIR}")
    print(f"Massif outputs will appear in: {MASSIF_OUTPUTS_DIR}")

    print("\nSubmitted Slurm jobs:")
    if submitted_jobs:
        for name in sorted(submitted_jobs.keys()):
            print(f"  Job Name: {name}, Job ID: {submitted_jobs[name]}")
    else:
        print("  No jobs were successfully submitted (or no executables found/matched). Check errors above.")

    print(f"\nMonitor job status using: squeue -u $USER")
    print(f"Check output logs (*.log) in '{SLURM_LOGS_DIR}'")
    print(f"Check massif files (massif.out.*) in '{MASSIF_OUTPUTS_DIR}' once jobs complete.")

    print("\nAfter the jobs complete:")
    print(f"1. Check the *.log files in {SLURM_LOGS_DIR} for execution times.")
    print("   Look for the 'real', 'user', and 'sys' times reported by the 'time' command.")
    print(f"2. Analyze the Massif output files in {MASSIF_OUTPUTS_DIR} using massif-visualizer:")
    print(f"   module load valgrind/3.21.0-gcc-8.5.0-genmsyy # Or appropriate valgrind module")

    # Update instructions for NPB BT massif files based on actual found executables
    if npb_bt_executables:
         print("   # NPB BT Massif files (check logs for which identifiers ran):")
         potential_identifiers = set()
         for npb_bt_exe_path in npb_bt_executables:
             match = npb_regex.match(npb_bt_exe_path.name)
             if match:
                 potential_identifiers.add(match.group(1))
         for npb_identifier in sorted(list(potential_identifiers)):
             massif_job_name = f"npb_bt_{npb_identifier}_massif"
             # Use correct path in instructions
             print(f"   massif-visualizer {MASSIF_OUTPUTS_DIR}/massif.out.{massif_job_name}")

    # SSCA2 massif files
    if ssca2_exe_path.exists() and os.access(ssca2_exe_path, os.X_OK):
        print("   # SSCA2 Massif files (one per scale):")
        for scale in SSCA2_SCALES:
          massif_job_name = f"ssca2_s{scale}_massif"
          # Use correct path in instructions
          print(f"   massif-visualizer {MASSIF_OUTPUTS_DIR}/massif.out.{massif_job_name}")
    print("   (You might need an X11 connection or VNC to view the visualizer GUI)")

