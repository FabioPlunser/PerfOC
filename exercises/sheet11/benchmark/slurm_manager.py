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


def wait_for_slurm_jobs(job_ids: list[str], check_interval: int = 10):
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
            squeue_cmd = [
                "squeue", 
                "-h",  
                '--me', 
            ]
            result = subprocess.run(
                squeue_cmd, capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                logger.error(
                    f"squeue command failed: {result.stderr}. Cannot monitor SLURM jobs."
                )
                return

            logger.debug(f"squeue output:\n{result.stdout}")

            for line in result.stdout.strip().splitlines():
                job_id = line.split()[0]
                if job_id not in active_job_ids:
                    logger.info(f"Job {job_id} is no longer tracked.")
                    if "interact" in line:
                        logger.info(f"Job {job_id} is an interactive job. Skipping.")
                        continue
                    
                    scancel_cmd = ["scancel", job_id]
                    try:
                        subprocess.run(scancel_cmd, check=True)
                        logger.info(f"Cancelled job {job_id} as it is no longer tracked.")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to cancel job {job_id}: {e}")
                
            active_job_ids = [
                line.split()[0] for line in result.stdout.strip().splitlines()
                if line.split()[0] in active_job_ids
            ] 

            
            logger.info(f"Still waiting for {len(active_job_ids)} SLURM jobs: {active_job_ids}")

        except FileNotFoundError:
            logger.error(
                "squeue command not found. Cannot monitor SLURM jobs. Please check manually."
            )
            return  
        except subprocess.CalledProcessError as e:
            logger.info(
                f"squeue error (possibly all jobs done): {e}. Assuming completion."
            )
            active_job_ids = []  
        except Exception as e:
            logger.error(f"An unexpected error occurred while checking job status: {e}")
            break  
    logger.info("All SLURM jobs have completed or are no longer tracked.")
