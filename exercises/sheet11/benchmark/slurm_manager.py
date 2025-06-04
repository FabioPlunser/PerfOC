import os
import subprocess
import time
import logging
from pathlib import Path
import config

logger = logging.getLogger(__name__)


def create_slurm_script(
    program_name: str,
    n_value: int,
    repetition: int,
    executable_path: Path,
    job_name: str,
):
    """Creates a SLURM submission script."""
    script_path = config.SLURM_SCRIPTS_DIR / f"{job_name}.sh"
    log_path = config.SLURM_LOGS_DIR / f"{job_name}.out"

    script_content = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={config.SLURM_PARTITION}
#SBATCH --cpus-per-task={config.SLURM_CPUS_PER_TASK}
#SBATCH --mem={config.SLURM_MEMORY}
#SBATCH --time={config.SLURM_TIME_LIMIT}
#SBATCH --output={log_path}
#SBATCH --error={log_path}

echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Running on: $(hostname)"
echo "Start time: $(date)"
echo "Program: {program_name}"
echo "N: {n_value}"
echo "Repetition: {repetition}"
echo "Executable: {executable_path}"
echo "----------------------------------------"

# The /usr/bin/time command provides detailed resource usage.
# -v flag for verbose output.
/usr/bin/time -v {executable_path} {n_value}

echo "----------------------------------------"
echo "End time: $(date)"
echo "Job completed."
"""
    with open(script_path, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    return script_path


def submit_slurm_job(script_path: Path) -> str | None:
    """Submits a SLURM job and returns the job ID."""
    try:
        result = subprocess.run(
            ["sbatch", str(script_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        job_id = result.stdout.strip().split()[-1]
        logger.info(f"Submitted job {job_id} from {script_path.name}")
        return job_id
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to submit SLURM job {script_path.name}: {e.stderr}")
        return None
    except FileNotFoundError:
        logger.error(
            "sbatch command not found. Ensure SLURM tools are installed and in PATH."
        )
        return None


def wait_for_slurm_jobs(job_ids: list[str], check_interval: int = 30):
    """Waits for a list of SLURM jobs to complete."""
    if not job_ids:
        logger.info("No SLURM jobs to wait for.")
        return

    active_job_ids = list(job_ids)
    total_jobs = len(active_job_ids)
    logger.info(f"Waiting for {total_jobs} SLURM job(s) to complete...")

    while active_job_ids:
        time.sleep(check_interval)
        try:
            # squeue -h -j job_id1,job_id2 -o "%i %T"
            # %i: Job ID, %T: State (compact form)
            squeue_cmd = [
                "squeue",
                "-h",
                "-j",
                ",".join(active_job_ids),
                "-o",
                "%i %T",
            ]
            result = subprocess.run(
                squeue_cmd, capture_output=True, text=True, check=False
            )

            if (
                result.returncode != 0
                and "Invalid job id specified" not in result.stderr
            ):
                # If squeue fails for reasons other than jobs not existing anymore
                logger.warning(
                    f"squeue command failed: {result.stderr}. Assuming jobs might have finished or errored."
                )
                # Potentially break or implement more robust error checking
                # For now, we'll let it try to parse what it got or assume jobs are done if output is empty

            current_running_jobs = []
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.strip().split()
                    job_id, status = parts[0], parts[1]
                    # Common SLURM states: PENDING (PD), RUNNING (R), COMPLETING (CG)
                    # Consider these as still active. Others (COMPLETED, FAILED, TIMEOUT, etc.) are finished.
                    if status in ["PD", "R", "CG"]:
                        current_running_jobs.append(job_id)

            active_job_ids = current_running_jobs
            completed_count = total_jobs - len(active_job_ids)
            logger.info(
                f"{completed_count}/{total_jobs} jobs completed. "
                f"{len(active_job_ids)} jobs remaining."
            )

        except FileNotFoundError:
            logger.error(
                "squeue command not found. Cannot monitor SLURM jobs. Please check manually."
            )
            return  # Stop trying if squeue is not available
        except subprocess.CalledProcessError as e:
            # This might happen if all jobs are already finished and squeue returns error for invalid job list
            logger.info(
                f"squeue error (possibly all jobs done): {e}. Assuming completion."
            )
            active_job_ids = []  # Assume all jobs are done
        except Exception as e:
            logger.error(f"An unexpected error occurred while checking job status: {e}")
            # Decide how to handle: continue, break, or re-raise
            break  # For safety, break loop on unexpected error

    logger.info("All SLURM jobs have completed or are no longer tracked.")
