import paramiko
import os
import subprocess
import statistics
import numpy as np
from scipy import stats
from models import Benchmark, BenchmarkResult, Host 

class BenchmarkService:
    def __init__(self, db_session):
        self.db_session = db_session

    def run_benchmark(self, benchmark_id):
        benchmark = self.db_session.query(Benchmark).get(benchmark_id)

        if benchmark.is_remote: 
            return self._run_remote_benchmark(benchmark) 
        else: 
            return self._run_local_benchmark(benchmark)

    def _run_local_benchmark(self, benchmark: Benchmark): 
        results = []

        for args_set in benchmark.command_line_args_sets: 
            set_results = self._run_with_args(benchmark, args_set, is_remote=False)
            results.append({
                "args": args_set, 
                "metrics": set_results
            })

        return self._analyze_results(results, benchmark)

    def _run_remote_benchmark(self, benchmark: Benchmark):
        host = self.db_session.query(Host).get(benchmark.host_id)

        self._copy_to_remote(benchmark, host)
        
        results = []

        if host.use_slur: 
            # Generate and submit Slurm jobs 
            for args_set in benchmark.command_line_args_sets: 
                job_id = self._submit_slurm_job(benchmark, host, args_set)
                # Wait for job completion and collect results 
                set_results = self._collect_slurm_results(job_id, host)
                results.append({
                    "args": args_set, 
                    "metrics": set_results
                })
        
        else: 
            # Direct SSH execution 
            for args_set in benchmark.command_line_args_sets: 
                set_results = self._run_with_args(benchmark, args_set, is_remote=True)
                results.append({
                    "args": args_set, 
                    "metrics": set_results
                })
        
        return self.analyze_results(results, benchmark)
    
    def _run_with_args(self, benchmark: Benchmark, args_set, is_remote=False):
        metrics_results = {metric: [] for metric in benchmark.metrics}

        # Determine number of repetitions dynamically 
        repetitions = benchmark.min_repetitions
        current_rep = 0 

        while current_rep < repetitions: 
            current_rep += 1
            
            if is_remote: 
                run_result = self._execute_remote(benchmark, args_set)
            else:
                run_result = self._execute_local(benchmark, args_set)
                
            for metric in benchmark
                metrics_results[metric].append(run_result[metric])
                
            if current_rep >= benchmark.min_repetitions:
                cofidence_reached = True 
                for metric, values in metrics_results.items(): 
                    if not self._check_confidence_interval(values, benchmark.confidence_level):
                        confidence_reached = False 
                        break
                    if confidence_reached or current_rep >= benchmark.max_repetitions:
                        break
                    
                    repetitions = min(current_rep + 5, benchmark.max_repetitions)

        final_results = {}
        for metric, values  in metrics_results.items():
            final_results[metric] = {
               "values": values, 
               "mean": statistics.mean(values),
               "median": statistics.median(values),
               "stdev": statistics.stdev(values),
               "variance": statistics.variance(values),
               "repetitions": len(values)
            }
        
        return final_results
    
    def _check_confidence_interval(self, values, confidence_level):
        if len(values) < 2:
            return False
        
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) / (len(values) ** 0.5)
        ci = stats.t.interval(confidence_level, len(values) - 1, loc=mean, scale=stdev)

        ci_width = ci[1] - ci[0]
        return ci_width / mean < 0.05 # 5% threshold
        
    def _execute_local(self, benchmark: Benchmark, args_set): 
        compile_defs = {}
        filtered_args = []

        for arg in args_set: 
            # Check if this is a compile-time definition 
            if arg.startswith("COMPILE:"): 
                key_value = arg[8:]
                if "="  in key_value: 
                    key, value = key_value.split("=", 1)
                    compile_defs[key] = value
            else:
                filtered_args.append(arg)

        # Check if we need to compile using cmake
        if benchmark.compile_arguments and "cmake" in benchmark.compile_arguments.lower(): 
             # Extract the source directory
            source_dir = benchmark.source_code_path
            
            # Create a unique build directory for this set of compile definitions
            # This ensures we don't mix binaries compiled with different definitions
            defs_hash = hash(frozenset(compile_defs.items()))
            build_dir = os.path.join(source_dir, f"build_{defs_hash}")
            os.makedirs(build_dir, exist_ok=True)
            
            # Change to build directory
            os.chdir(build_dir)
            
            # Prepare CMake flags for compile-time definitions
            cmake_defs = ""
            for key, value in compile_defs.items():
                cmake_defs += f" -D{key}={value}"
            
            # Run CMake configuration with compile-time definitions
            cmake_config_cmd = f"cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release"
            
            # Add C flags for preprocessor definitions
            c_flags = " ".join([f"-D{key}={value}" for key, value in compile_defs.items()])
            if c_flags:
                cmake_config_cmd += f' -DCMAKE_C_FLAGS="{c_flags}"'
            
            # Add any custom CMake arguments from benchmark.compile_arguments
            if "-D" in benchmark.compile_arguments:
                cmake_config_cmd += f" {benchmark.compile_arguments}"
                
            subprocess.run(cmake_config_cmd, shell=True, check=True)
            
            # Run build
            build_cmd = "ninja"
            subprocess.run(build_cmd, shell=True, check=True)
            
            # Change back to original directory
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            
            # Update execution directory to use the specific build directory
            exec_dir = build_dir
        
        elif benchmark.compile_arguments:
            # Handle non-CMake compilation with compile-time definitions
            c_flags = " ".join([f"-D{key}={value}" for key, value in compile_defs.items()])
            compile_cmd = f"cd {benchmark.source_code_path} && {benchmark.compile_arguments} CFLAGS=\"{c_flags}\""
            subprocess.run(compile_cmd, shell=True, check=True)
            
            # Use the specified execution directory or source directory
            exec_dir = benchmark.execution_folder or benchmark.source_code_path
        else:
            # No compilation needed
            exec_dir = benchmark.execution_folder or benchmark.source_code_path
            
        # Build command - for CMake builds with definitions, use the specific build directory
        if "cmake" in (benchmark.compile_arguments or "").lower():
            executable = os.path.join(exec_dir, benchmark.output_path)
        else:
            executable = os.path.join(benchmark.source_code_path, benchmark.output_path)
        
        cmd = f"cd {exec_dir} && {executable} {' '.join(filtered_args)}"
        
        # Execute and capture output
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Parse output to extract metrics
        metrics_result = self._parse_metrics(result.stdout, result.stderr, benchmark.metrics)
        
        # Add compile-time definitions to the result for reference
        metrics_result["compile_definitions"] = compile_defs
        
        return metrics_result
        
