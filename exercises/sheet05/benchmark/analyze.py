import re
import statistics
from pathlib import Path
import pandas as pd
import numpy as np

import config # For subdirs

def parse_slurm_log(log_path: Path):
    """
    Parses a Slurm log file to find the 'real' time from 'time -p',
    handling both '.' and ',' as decimal separators.
    """
    if not log_path.is_file(): return None, "missing"
    try:
        with open(log_path, 'r', errors='ignore') as f: content = f.read()

        # --- Error Checking Logic (remains the same) ---
        is_error = False
        if "slurmstepd: error:" in content or "ERROR" in content or "Failed" in content:
             is_error = True # Mark potential error, check exit code later

        exit_match = re.search(r"Command finished with exit code: (\d+)", content)
        exit_code_str = exit_match.group(1) if exit_match else None
        exit_code_int = int(exit_code_str) if exit_code_str is not None else None

        if is_error:
            if exit_code_int is not None and exit_code_int != 0:
                return None, "program_error" # Error keyword + non-zero exit = program error
            else:
                # Error keyword but zero or missing exit code = likely Slurm/setup error
                return None, "slurm_error"

        # --- Time Extraction (Modified Regex) ---
        # Match digits, allow comma OR period as separator
        match = re.search(r"^real\s+([\d.,]+)", content, re.MULTILINE)

        if match:
            time_str = match.group(1)
            # Normalize the time string (replace comma with period)
            time_str_normalized = time_str.replace(',', '.')
            try:
                real_time = float(time_str_normalized)
            except ValueError:
                 print(f"ERROR: Could not convert time string '{time_str}' (normalized: '{time_str_normalized}') to float in {log_path}")
                 return None, "parse_error" # Failed to convert time

            # --- Success Check (using previously extracted exit code) ---
            if exit_code_int == 0:
                 return real_time, "success" # Time found AND exit code is 0
            else:
                 # Time found, but exit code is non-zero or missing
                 return None, "program_error"
        else:
            # Time regex did not match
            # Check if it exited cleanly anyway (maybe time failed?)
            if exit_code_int == 0:
                 print(f"WARNING: Log {log_path.name} finished with exit code 0 but 'real time' line not found or parsed.")
                 return None, "no_time_found" # Or maybe "program_error"? Depends on expectation.
            else:
                 # No time found AND exit code non-zero/missing
                 return None, "program_error" # Default to program error if time is missing and exit wasn't clean

    except Exception as e:
        print(f"ERROR: Parsing log file {log_path}: {e}")
        return None, "parse_error"

# --- analyze_log_files function remains the same ---
# (It uses the return values from the corrected parse_slurm_log)
def analyze_log_files(programs_to_run, flag_configs, num_runs, base_output_dir):
    """Parses all relevant logs, aggregates data, and returns a DataFrame."""
    print("\n--- Analyzing Results ---")
    logs_dir = base_output_dir / config.SLURM_LOGS_SUBDIR
    print(f"INFO: Analyzing logs in: {logs_dir}")

    if not programs_to_run:
        print("INFO: No programs were selected to run, skipping analysis.")
        return None

    results_data = []
    total_logs_expected = len(programs_to_run) * len(flag_configs) * num_runs
    logs_processed = 0
    logs_missing = 0
    logs_parsed_error = 0
    successful_runs = 0
    program_errors = 0
    slurm_errors = 0
    no_time_errors = 0


    for prog in programs_to_run:
        prog_name = prog['name']
        # Use the sanitized flags ID consistent with build/results structure
        for flags_id_orig, flags_list in flag_configs.items():
            run_times = []
            statuses = []
            flags_string = " ".join(sorted(flags_list)) # Recreate for storage
            # Need the sanitized ID to match build structure if different from original key
            # This assumes utils.sanitize_flags is available or logic is replicated
            # For simplicity here, assume flags_id_orig is the key used everywhere
            # If build.py uses sanitized_flags_id, analysis needs it too.
            # Let's assume flags_id_orig IS the key used throughout for now.
            flags_id = flags_id_orig


            for i in range(num_runs):
                logs_processed += 1
                # Construct job name using the consistent flags_id
                job_name = f"{prog_name}_{flags_id}_run{i + 1}"
                log_file = logs_dir / f"{job_name}.log"
                real_time, status = parse_slurm_log(log_file)
                statuses.append(status)

                if status == "success":
                    run_times.append(real_time)
                    successful_runs += 1
                else:
                    run_times.append(np.nan)
                    if status == "missing": logs_missing += 1
                    elif status == "parse_error": logs_parsed_error += 1
                    elif status == "program_error": program_errors += 1
                    elif status == "slurm_error": slurm_errors += 1
                    elif status == "no_time_found": no_time_errors += 1


            # Calculate stats, ignoring NaNs
            mean_time = np.nanmean(run_times) if not all(np.isnan(run_times)) else np.nan
            stdev_time = np.nanstd(run_times) if np.count_nonzero(~np.isnan(run_times)) > 1 else 0.0
            success_count = np.count_nonzero(~np.isnan(run_times))

            results_data.append({
                "Program": prog_name,
                "FlagsID": flags_id, # Store the ID used for matching logs/builds
                "FlagsStr": flags_string, # Store the full flags string
                "MeanTime": mean_time,
                "StdDev": stdev_time,
                "Runs": success_count, # Number of successful runs found
                "RawTimes": run_times, # Store list of times (incl NaNs)
                "Statuses": statuses, # Store list of statuses
            })

    print(f"\n--- Analysis Summary ---")
    print(f"Expected logs: {total_logs_expected}")
    print(f"Logs processed/checked: {logs_processed}")
    print(f"Successful runs found: {successful_runs}")
    print(f"Missing log files: {logs_missing}")
    print(f"Log parsing errors: {logs_parsed_error}")
    print(f"Program errors (non-zero exit or missing time): {program_errors}")
    print(f"Slurm/Setup errors: {slurm_errors}")
    print(f"Runs with no time found (but exit 0): {no_time_errors}")


    if not results_data:
         print("ERROR: No results could be parsed. Cannot proceed.")
         return None

    # --- Create DataFrame ---
    df = pd.DataFrame(results_data)

    # Ensure FlagsID is treated consistently (string for general case)
    df['FlagsID'] = df['FlagsID'].astype(str)

    # Try to make FlagsID categorical if it matches default levels for sorting
    unique_flags = df['FlagsID'].unique()
    if all(fid in config.DEFAULT_OPTIMIZATION_LEVELS for fid in unique_flags):
         opt_order = pd.CategoricalDtype(config.DEFAULT_OPTIMIZATION_LEVELS, ordered=True)
         df['FlagsID'] = df['FlagsID'].astype(opt_order)
         df = df.sort_values(by=['Program', 'FlagsID'])
    else:
         # Sort alphabetically otherwise
         # Convert to numeric if possible for better sorting of O2_plus_... flags
         try:
              # Attempt a natural sort if possible (e.g., O2_plus_10 before O2_plus_2)
              # This requires external library like natsort or complex regex sort key
              # Simple alphabetical sort for now:
              df = df.sort_values(by=['Program', 'FlagsID'])
         except TypeError: # Fallback if mixing types
              df = df.sort_values(by=['Program', 'FlagsID'])


    # --- Save results ---
    results_dir = base_output_dir / config.RESULTS_SUBDIR
    raw_csv_path = results_dir / "benchmark_results_raw.csv"
    summary_csv_path = results_dir / "benchmark_summary_mean_time.csv"
    try:
        # Ensure results dir exists
        results_dir.mkdir(parents=True, exist_ok=True)

        df.to_csv(raw_csv_path, index=False, float_format='%.6f')
        print(f"INFO: Raw results saved to: {raw_csv_path}")

        # Pivot for the summary table (MeanTime), using FlagsID as columns
        # Handle potential non-unique index/columns if errors occurred during setup
        try:
            # Use FlagsID (which should now be string or categorical)
            summary_table = df.pivot_table(index='Program', columns='FlagsID', values='MeanTime', aggfunc='mean') # Use pivot_table for robustness
            summary_table.to_csv(summary_csv_path, float_format='%.4f')
            print(f"INFO: Summary table (Mean Times) saved to: {summary_csv_path}")
        except Exception as pivot_e:
             print(f"ERROR: Could not create pivot summary table: {pivot_e}")
             print("INFO: Saving non-pivoted mean times instead.")
             summary_alt = df[['Program', 'FlagsID', 'MeanTime', 'StdDev', 'Runs']].copy()
             summary_alt.to_csv(summary_csv_path, index=False, float_format='%.4f')


        print("INFO: Analysis finished.")
        return df

    except Exception as e:
        print(f"ERROR: Failed to save analysis results to CSV: {e}")
        return None
