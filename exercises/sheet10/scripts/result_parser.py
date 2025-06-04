#!/usr/bin/env python3

import re
import logging
from pathlib import Path
import pandas as pd

from config import NUM_REPETITIONS

logger = logging.getLogger(__name__)


class ResultParser:
    def parse_benchmark_output(self, log_path, combination, run_id):
        """Parse benchmark output from SLURM log file."""
        if not log_path.exists():
            logger.warning(f"Log file not found: {log_path}")
            return None
        
        try:
            with open(log_path, "r") as f:
                content = f.read()
            
            data = {
                "container": combination["container"],
                "size": combination["size"],
                "elem_size": combination["elem_size"],
                "ratio": combination["ratio"],
                "test_duration": combination["test_duration"],
                "random_access" : combination["random_access"],
                "run_id": run_id,
            }
            
            # Extract benchmark metrics - updated patterns for new benchmark format
            patterns = {
                "operations_completed": r"Operations completed: (\d+)",
                "ops_per_second": r"Operations per second: ([\d\.]+)",
                "actual_time_s": r"Actual benchmark time: ([\d\.]+) seconds",
                "validation_checksum": r"Validation checksum: (-?\d+)",
            }
            
            # Linux GNU time patterns
            linux_time_patterns = {
                "peak_memory_kb": r"Maximum resident set size \(kbytes\): (\d+)",
                "user_time_s": r"User time \(seconds\): ([\d\.]+)",
                "system_time_s": r"System time \(seconds\): ([\d\.]+)",
            }
            
            # macOS time patterns (different format)
            macos_time_patterns = {
                "peak_memory_kb": r"maximum resident set size\s+(\d+)",
                "user_time_s": r"(\d+\.\d+) user",
                "system_time_s": r"(\d+\.\d+) sys",
            }
            
            # Extract basic benchmark metrics
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    if key in ["operations_completed", "validation_checksum"]:
                        data[key] = int(match.group(1))
                    else:
                        data[key] = float(match.group(1))
            
            # Try Linux time patterns first
            time_patterns_found = False
            for key, pattern in linux_time_patterns.items():
                match = re.search(pattern, content)
                if match:
                    time_patterns_found = True
                    if key == "peak_memory_kb":
                        data[key] = int(match.group(1))
                    else:
                        data[key] = float(match.group(1))
            
            # If Linux patterns not found, try macOS patterns
            if not time_patterns_found:
                for key, pattern in macos_time_patterns.items():
                    match = re.search(pattern, content)
                    if match:
                        if key == "peak_memory_kb":
                            # macOS reports in bytes, convert to KB
                            data[key] = int(match.group(1)) // 1024
                        else:
                            data[key] = float(match.group(1))
            
            # Calculate additional metrics
            if "peak_memory_kb" in data:
                data["peak_memory_mb"] = data["peak_memory_kb"] / 1024
            
            # Check for errors
            data["error"] = "ERROR" in content or "Segmentation fault" in content
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse {log_path}: {e}")
            return None
    
    def collect_all_results(self, combinations, logs_dir):
        """Collect results from all benchmark runs."""
        all_results = []
        
        for i, combination in enumerate(combinations):
            for run_id in range(1, NUM_REPETITIONS + 1):
                job_name = f"bench_{i:03d}_run{run_id}"
                log_path = logs_dir / f"{job_name}.out"
                
                result = self.parse_benchmark_output(log_path, combination, run_id)
                if result:
                    all_results.append(result)
        
        return pd.DataFrame(all_results)
    
    def collect_local_results(self, local_results):
        """Collect results from local benchmark runs."""
        all_results = []
        
        for result in local_results:
            if result["success"] and result["result_file"]:
                # Parse the result file
                parsed = self.parse_benchmark_output(
                    result["result_file"],
                    result["combination"], 
                    result["repetition"]
                )
                if parsed:
                    all_results.append(parsed)
        
        return pd.DataFrame(all_results)
