#!/usr/bin/env python3

import os
import subprocess
import time
import itertools
import logging
from pathlib import Path
import json

from config import (
    DATA_STRUCTURES, RATIOS, ELEMENT_SIZES, NUM_ELEMENTS, TEST_DURATION, RANDOM_ACCESS,
    SLURM_PARTITION, SLURM_CPUS_PER_TASK, SLURM_MEMORY, SLURM_TIME_LIMIT,
    NUM_REPETITIONS
)

logger = logging.getLogger(__name__)


class SlurmManager:
    def __init__(self, scripts_dir, logs_dir, executable_path):
        self.scripts_dir = Path(scripts_dir)
        self.logs_dir = Path(logs_dir)
        self.executable_path = Path(executable_path)
    
    def estimate_memory_usage(self, num_elements, element_size):
        """Estimate memory usage in MB."""
        base_memory = num_elements * element_size / (1024 * 1024)
        
        if element_size == 8:
            overhead = num_elements * 16 / (1024 * 1024)
        else:
            overhead = num_elements * (element_size + 16) / (1024 * 1024)
        
        extra_space = base_memory * 0.1
        return base_memory + overhead + extra_space
    
    def should_exclude_combination(self, ds, num_elements, element_size):
        """Determine if combination should be excluded."""
        memory_mb = self.estimate_memory_usage(num_elements, element_size)
        
        if memory_mb > 12 * 1024:
            logger.info(
                f"Excluding {ds} with {num_elements} elements of {element_size} bytes "
                f"(estimated {memory_mb:.1f} MB)"
            )
            return True
        
        if ds.startswith("list") and num_elements >= 1000000 and element_size >= 512:
            logger.info(f"Excluding slow combination: {ds}")
            return True
        
        return False
    
    def generate_combinations(self):
        """Generate all valid benchmark combinations."""
        combinations = []
        excluded_count = 0
        
        for ds, ratio, num_elem, elem_size, random_access in itertools.product(
            DATA_STRUCTURES, RATIOS, NUM_ELEMENTS, ELEMENT_SIZES, RANDOM_ACCESS
        ):
            if self.should_exclude_combination(ds, num_elem, elem_size):
                excluded_count += 1
                continue
            
            combinations.append({
                "container": ds,
                "size": num_elem,
                "elem_size": elem_size,
                "ratio": ratio,
                "test_duration": TEST_DURATION,
                "estimated_memory_mb": self.estimate_memory_usage(num_elem, elem_size),
                "random_access": random_access,
            })
        
        logger.info(f"Generated {len(combinations)} combinations, excluded {excluded_count}")
        return combinations
    
    def create_slurm_script(self, combination, run_id, job_name):
        """Create SLURM script for a benchmark combination."""
        script_path = self.scripts_dir / f"{job_name}.sh"
        log_path = self.logs_dir / f"{job_name}.out"
        
        script_content = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={SLURM_PARTITION}
#SBATCH --cpus-per-task={SLURM_CPUS_PER_TASK}
#SBATCH --mem={SLURM_MEMORY}
#SBATCH --time={SLURM_TIME_LIMIT}
#SBATCH --output={log_path}
#SBATCH --error={log_path}

# Change to benchmark directory
cd {self.executable_path.parent}

# Ensure benchmark executable exists
if [ ! -f "{self.executable_path}" ]; then
    echo "ERROR: Benchmark executable not found at {self.executable_path}"
    exit 1
fi

# Run benchmark with timing
echo "Starting benchmark: {job_name}"
echo "Container: {combination['container']}"
echo "Size: {combination['size']}"
echo "Element Size: {combination['elem_size']} bytes"
echo "Ratio: {combination['ratio']}"
echo "Test Duration: {combination['test_duration']} seconds"
echo "Random Acess: {combination['random_access']}"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v {self.executable_path} \\
    {combination['container']} \\
    {combination['size']} \\
    {combination['elem_size']} \\
    {combination['ratio']} \\
    {combination['test_duration']} \\
    {combination['random_access']}

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
"""
        
        with open(script_path, "w") as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
        return script_path, log_path
    
    def submit_slurm_job(self, script_path):
        """Submit SLURM job and return job ID."""
        try:
            
            result = subprocess.run(
                ["sbatch", str(script_path)], 
                capture_output=True, text=True, check=True
            )
            job_id = result.stdout.strip().split()[-1]
            return job_id
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to submit job {script_path}: {e}")
            return None
    
    def submit_all_jobs(self, combinations):
        """Submit all benchmark jobs."""
        job_ids = []
        
        for i, combination in enumerate(combinations):
            for run_id in range(1, NUM_REPETITIONS + 1):
                job_name = f"bench_{i:03d}_run{run_id}"
                script_path, log_path = self.create_slurm_script(
                    combination, run_id, job_name
                )
                
                job_id = self.submit_slurm_job(script_path)
                if job_id:
                    job_ids.append(job_id)
                    logger.info(f"Submitted job {job_id}: {job_name}")
        
        logger.info(f"Submitted {len(job_ids)} jobs to SLURM")
        return job_ids
    
    def wait_for_jobs(self, job_ids, check_interval=30):
        """Wait for all SLURM jobs to complete."""
        logger.info(f"Waiting for {len(job_ids)} jobs to complete...")
        
        while job_ids:
            time.sleep(check_interval)
            
            try:
                result = subprocess.run(
                    ["squeue", "-j", ",".join(job_ids), "-h", "-o", "%i %T"],
                    capture_output=True, text=True, check=True,
                )
                
                running_jobs = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        job_id, status = line.strip().split()
                        if status in ["PENDING", "RUNNING"]:
                            running_jobs.append(job_id)
                
                completed = len(job_ids) - len(running_jobs)
                logger.info(f"Jobs completed: {completed}/{len(job_ids)}")
                job_ids = running_jobs
                
            except subprocess.CalledProcessError:
                logger.info("Could not check job status, assuming completion")
                break
        
        logger.info("All jobs completed!")
