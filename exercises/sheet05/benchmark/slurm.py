# slurm.py
import os
import stat
import re
import time
from pathlib import Path

import config
from utils import run_command

def generate_slurm_script(prog_name, flags_id, run_index, num_runs,
                          build_dir, exe_rel_path, run_args,
                          base_output_dir):
    """Generates a Slurm script for a specific run configuration."""
    job_name = f"{prog_name}_{flags_id}_run{run_index + 1}"
    scripts_dir = base_output_dir / config.SLURM_SCRIPTS_SUBDIR
    logs_dir = base_output_dir / config.SLURM_LOGS_SUBDIR
    slurm_script_path = scripts_dir / f"{job_name}.sh"
    slurm_log_path = logs_dir / f"{job_name}.log"

    # Ensure scripts/logs dirs exist (should be done by main CLI, but safe check)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Command to run inside Slurm
    # Ensure run_args with relative paths are handled correctly if needed
    # (Current config assumes absolute path for QAP data file)
    run_command_parts = [f"./{exe_rel_path}"] + run_args
    timed_command = ["time", "-p"] + run_command_parts

    script_content = f"""#!/bin/bash
#SBATCH --partition={config.SLURM_PARTITION}
#SBATCH --job-name={job_name}
#SBATCH --output={slurm_log_path.resolve()}
#SBATCH --error={slurm_log_path.resolve()}
#SBATCH --ntasks={config.SLURM_NTASKS}
#SBATCH --nodes={config.SLURM_NODES}
#SBATCH --cpus-per-task={config.SLURM_CPUS_PER_TASK}
#SBATCH --time={config.SLURM_TIME}
#SBATCH --exclusive

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Run Index: {run_index + 1}/{num_runs}"
echo "Program: {prog_name}"
echo "Flags ID: {flags_id}"
echo "Build Dir: {build_dir.resolve()}"
echo "Log File: {slurm_log_path.resolve()}"
echo "Job started at: $(date)"

echo "--- Loading Modules ---"
module purge
{chr(10).join([f"module load {mod}" for mod in config.MODULES_TO_LOAD])}
echo "Loaded modules:"
module list

echo "--- Execution ---"
echo "Changing directory to: {build_dir.resolve()}"
cd "{build_dir.resolve()}" || exit 1

echo "Running command: {' '.join(timed_command)}"
echo "-------------------- Program Output Start --------------------"

{' '.join(timed_command)}

exit_code=$?
echo "-------------------- Program Output End ----------------------"
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

# Basic check for timing info
if grep -q "real" "{slurm_log_path.resolve()}"; then
    echo "Timing information should be present in the log."
else
    echo "WARNING: Timing information ('real') might be missing from the log."
fi

exit $exit_code
"""
    try:
        with open(slurm_script_path, "w") as f:
            f.write(script_content)
        slurm_script_path.chmod(slurm_script_path.stat().st_mode | stat.S_IEXEC)
        # print(f"DEBUG Generated Slurm script: {slurm_script_path}") # Less verbose
        return slurm_script_path
    except Exception as e:
        print(f"ERROR: Failed to write/chmod Slurm script {slurm_script_path}: {e}")
        return None

def submit_slurm_job(script_path: Path):
    """Submits a Slurm script using sbatch."""
    sbatch_cmd = ["sbatch", str(script_path)]
    try:
        result = run_command(sbatch_cmd, check=True, capture=True, verbose=False) # Less verbose
        job_id_match = re.search(r"Submitted batch job (\d+)", result.stdout)
        if job_id_match:
            return job_id_match.group(1)
        else:
            print(f"WARNING: Submitted job but could not parse Job ID from output: {result.stdout}")
            return "UNKNOWN"
    except Exception as e:
        print(f"ERROR: Failed to submit job from {script_path.name}: {e}")
        return None

def run_slurm_benchmarks(programs_to_run, flag_configs, build_results, num_runs, base_output_dir, submit=True):
    """Generates and optionally submits Slurm jobs for all configurations."""
    print("\n--- Running Benchmarks (Generating/Submitting Slurm Jobs) ---")
    submitted_jobs = {} # { job_name: job_id }
    total_scripts_generated = 0
    total_scripts_failed = 0
    submission_failures = 0
    build_missing_count = 0

    if not programs_to_run:
        print("INFO: No programs selected for running.")
        return {}

    for prog in programs_to_run:
        prog_name = prog['name']
        for flags_id, flags_list in flag_configs.items():
            # Find the corresponding build result
            build_key = (prog_name, flags_id)
            exe_path = build_results.get(build_key)

            if not exe_path or not exe_path.is_file():
                print(f"WARNING: Executable for {prog_name} / {flags_id} not found or build failed. Skipping runs.")
                build_missing_count += (num_runs) # Count all potential runs as skipped
                total_scripts_failed += num_runs
                continue # Skip runs for this config

            build_dir = exe_path.parent
            exe_rel_path = Path(prog['exe_subdir']) / prog['exe_name']

            for i in range(num_runs):
                script_path = generate_slurm_script(
                    prog_name, flags_id, i, num_runs,
                    build_dir, exe_rel_path, prog['run_args'],
                    base_output_dir
                )
                if script_path:
                    total_scripts_generated += 1
                    if submit:
                        job_id = submit_slurm_job(script_path)
                        if job_id:
                            job_name = f"{prog_name}_{flags_id}_run{i + 1}"
                            submitted_jobs[job_name] = job_id
                        else:
                            submission_failures += 1
                        time.sleep(0.05) # Shorter delay
                else:
                    total_scripts_failed += 1

    print("\n--- Slurm Job Generation/Submission Summary ---")
    print(f"Total runs planned (based on successful builds): {total_scripts_generated + total_scripts_failed - build_missing_count}")
    if build_missing_count > 0:
        print(f"Skipped {build_missing_count} runs due to missing/failed builds.")
    if total_scripts_failed > build_missing_count:
         print(f"ERROR: Failed to generate {total_scripts_failed - build_missing_count} Slurm scripts.")
    print(f"Successfully generated {total_scripts_generated} Slurm scripts in: {base_output_dir / config.SLURM_SCRIPTS_SUBDIR}")

    if submit:
        print(f"Attempted to submit {total_scripts_generated} jobs.")
        print(f"Successfully submitted {len(submitted_jobs)} jobs.")
        if submission_failures > 0: print(f"ERROR: Failed to submit {submission_failures} jobs.")
        print("\nSubmitted Job IDs:")
        if submitted_jobs:
            # Limited printout for brevity
            count = 0
            for name, jid in sorted(submitted_jobs.items()):
                print(f"  {name}: {jid}")
                count += 1
                if count >= 10 and len(submitted_jobs) > 15:
                     print(f"  ... ({len(submitted_jobs) - count} more)")
                     break
        else: print("  None.")
        print(f"\nMonitor job status using: squeue -u $USER")
        print(f"Logs will appear in: {base_output_dir / config.SLURM_LOGS_SUBDIR}")
        print("INFO: Wait for all jobs to complete before running analysis.")
    else:
        print("INFO: Jobs were not submitted.")
        if total_scripts_generated > 0:
             print(f"You can submit them manually via: find {base_output_dir / config.SLURM_SCRIPTS_SUBDIR} -name '*.sh' -exec sbatch {{}} \\;")

    return submitted_jobs
