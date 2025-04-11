#!/usr/bin/env python3
# benchmark_cli.py
import argparse
import sys
from pathlib import Path
import copy
import json
import re
import pandas as pd 
import numpy as np

# Import functions from our modules
import config
import utils
import build
import slurm
import analyze
import report

def load_program_definitions(config_file_path):
    """Loads program definitions from the JSON file."""
    if not config_file_path.is_file():
        print(f"ERROR: Program configuration file not found: {config_file_path}")
        return None
    try:
        with open(config_file_path, 'r') as f:
            programs_data = json.load(f)
        # Basic validation (check if it's a list)
        if not isinstance(programs_data, list):
            print(f"ERROR: Invalid format in {config_file_path}. Expected a JSON list.")
            return None
        # Validate absolute paths
        for i, pdef in enumerate(programs_data):
            if 'src_dir' not in pdef:
                 print(f"ERROR: Program definition {i} ('{pdef.get('name', 'UNKNOWN')}') is missing 'src_dir'.")
                 return None
            if not Path(pdef['src_dir']).is_absolute():
                 print(f"ERROR: 'src_dir' for program '{pdef.get('name', 'UNKNOWN')}' ('{pdef['src_dir']}') must be an absolute path.")
                 return None
            if not Path(pdef['src_dir']).is_dir():
                 print(f"WARNING: Source directory '{pdef['src_dir']}' for program '{pdef.get('name', 'UNKNOWN')}' does not exist or is not a directory.")
                 # Allow continuing, build step will likely fail later

        print(f"INFO: Successfully loaded {len(programs_data)} program definitions from {config_file_path}")
        return programs_data
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON file {config_file_path}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Failed to read program config file {config_file_path}: {e}")
        return None

# Removed parse_program_request function as it's no longer needed for CLI input

def prepare_program_configurations(all_program_defs):
    """
    Creates specific program instance configurations for ALL programs
    defined in the JSON, expanding identity parameters.
    Assumes src_dir in definitions is absolute.
    """
    programs_to_run = []
    print("\n--- Preparing Program Configurations ---")

    for base_config in all_program_defs:
        base_name = base_config['name']
        defined_params = base_config.get("parameters", {})
        identity_param_key = None
        identity_param_info = None
        identity_options = []

        # Check for an identity parameter to expand
        for param_key, param_info in defined_params.items():
            if param_info.get("type") == "identity" and param_info.get("cli_suffix"):
                identity_param_key = param_key
                identity_param_info = param_info
                identity_options = param_info.get("options", [])
                if not identity_options and "default" in param_info:
                    identity_options = [param_info["default"]] # Use default if no options
                elif not identity_options:
                     print(f"WARNING: Identity parameter '{param_key}' for '{base_name}' has no options or default. Skipping expansion.")
                break # Assume only one such parameter per definition

        # Determine instances to create
        instances_to_create = []
        if identity_param_key and identity_options:
            # Create one instance per identity option
            for option_value in identity_options:
                instances_to_create.append({identity_param_key: option_value})
        else:
            # Create a single instance (using default for identity if needed)
            single_instance_params = {}
            if identity_param_key and "default" in identity_param_info:
                 single_instance_params[identity_param_key] = identity_param_info["default"]
            instances_to_create.append(single_instance_params)

        # Configure each instance
        for instance_params in instances_to_create:
            prog = copy.deepcopy(base_config) # Start with a copy of the base definition
            instance_name = base_name # Default instance name

            # Apply identity parameter value and determine instance name
            if identity_param_key and identity_param_key in instance_params:
                id_value = instance_params[identity_param_key]
                fmt = identity_param_info.get("name_format", "{base}_{value}")
                instance_name = fmt.format(base=base_name, value=id_value)
                print(f"DEBUG Configuring instance '{instance_name}' from base '{base_name}' with {identity_param_key}={id_value}")
            else:
                 print(f"DEBUG Configuring instance '{instance_name}' from base '{base_name}' (no identity expansion or default)")

            prog['name'] = instance_name # Set the unique name for this instance

            # --- Apply Parameters (Defaults and Identity) ---
            prog['run_args'] = []
            prog['compile_defs'] = []

            # Use instance_params (identity) + defaults for others
            current_params = {}
            for param_key, param_info in defined_params.items():
                 if param_key in instance_params: # Value from identity expansion
                      current_params[param_key] = instance_params[param_key]
                 elif "default" in param_info: # Use default value
                      current_params[param_key] = param_info["default"]
                 # Else: parameter defined but no value/default, skip applying

            # Apply the determined parameters
            for param_key, value in current_params.items():
                param_info = defined_params[param_key] # We know this exists
                param_type = param_info.get("type")

                # Format and add based on type
                if param_type == "runtime":
                    if param_info.get("is_path"):
                        # Resolve path relative to the program's absolute src_dir
                        try:
                            # Ensure src_dir is absolute Path object
                            src_dir_path = Path(prog['src_dir']).resolve()
                            # Ensure value is treated as string for path joining
                            resolved_path = str((src_dir_path / str(value)).resolve())
                            prog['run_args'].append(resolved_path)
                        except Exception as e:
                            print(f"ERROR: Could not resolve runtime path for param {param_key}='{value}' in {instance_name}: {e}")
                            # Decide how to handle error - skip program instance? Mark as invalid?
                    else:
                        prog['run_args'].append(str(value)) # Ensure runtime args are strings
                elif param_type == "compile":
                    fmt = param_info.get("format", "-D{key}={value}")
                    prog['compile_defs'].append(fmt.format(key=param_key, value=value))
                elif param_type == "identity":
                    # Handle updates based on identity param (e.g., NPB class)
                    if param_info.get("updates_exe_name"):
                        prog['exe_name'] = instance_name # Assumes name_format matches exe
                    if param_info.get("updates_cmake_target"):
                        prog['cmake_target'] = instance_name # Assumes name_format matches target

            # --- Final Setup (Paths) ---
            # src_dir is already absolute from JSON, just resolve/validate
            try:
                 prog['src_dir'] = Path(prog['src_dir']).resolve()
                 if not prog['src_dir'].is_dir():
                      print(f"ERROR: Source directory for '{prog['name']}' not found or not a directory: {prog['src_dir']}")
                      continue # Skip this program instance
            except Exception as e:
                 print(f"ERROR: Invalid source directory path for '{prog['name']}': {prog['src_dir']}. Error: {e}")
                 continue # Skip

            programs_to_run.append(prog)

    return programs_to_run


def main():
    parser = argparse.ArgumentParser(
        description="GCC Optimization Benchmarking Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # --- Removed Program Selection Args ---
    # parser.add_argument(
    #     '-p', '--programs', nargs='+', required=True, ...)
    # parser.add_argument(
    #     '--small-samples-dir', type=Path, ...) # No longer needed for src_dir
    # parser.add_argument(
    #     '--large-samples-dir', type=Path, ...) # No longer needed for src_dir

    # --- Kept Other Args ---
    parser.add_argument(
        '--config-file', type=Path, default=config.DEFAULT_PROGRAM_CONFIG_FILE,
        help="Path to the JSON file defining programs and parameters (must use absolute paths for 'src_dir')."
    )
    parser.add_argument(
        '--output-dir', type=Path, default=Path("./benchmark_output"),
        help="Base directory for all build files, logs, and results."
    )
    parser.add_argument(
        '--num-runs', type=int, default=config.DEFAULT_NUM_RUNS,
        help="Number of times to run each program configuration."
    )
    parser.add_argument(
        '--flags-mode',
        choices=['levels', 'o2_vs_o3_diff', 'o2_to_o3_cumulative'], # Added new choice
        default='levels',
        help=(
            "Which set of flag configurations to test: "
            "'levels' for O0-Ofast, "
            "'o2_vs_o3_diff' for individual O3 flags added to O2 (Exercise B default), "
            "'o2_to_o3_cumulative' for adding O3 flags cumulatively to O2."
        )
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true', help="Enable verbose output."
    )
    # Add subparsers or other arguments as needed...
    parser.add_argument('--force-rebuild', action='store_true', help="Force rebuild even if executables exist.")
    parser.add_argument('--submit', action='store_true', help="Actually submit Slurm jobs (default is generate only).")
    parser.add_argument('--action', choices=['full-run', 'build', 'run', 'analyze', 'report'], default='full-run', help="Action to perform.")
    parser.add_argument('--skip-build', action='store_true', help="Skip build stage.")
    parser.add_argument('--skip-run', action='store_true', help="Skip run stage (Slurm generation/submission).")
    parser.add_argument('--skip-analyze', action='store_true', help="Skip analysis stage.")
    parser.add_argument('--skip-report', action='store_true', help="Skip report stage.")
    parser.add_argument('--results-csv', type=Path, help="Path to existing raw results CSV for report/analyze stage.")


    args = parser.parse_args()

    # --- Initial Setup ---
    print("--- GCC Optimization Benchmarking Tool ---")
    print(f"INFO: Output directory: {args.output_dir.resolve()}")
    print(f"INFO: Using program config: {args.config_file.resolve()}")
    print(f"INFO: Number of runs per config: {args.num_runs}")
    print(f"INFO: Flags mode: {args.flags_mode}")
    print(f"INFO: Action: {args.action}")

    if not utils.load_modules(verbose=args.verbose): sys.exit(1)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not utils.ensure_output_dirs(args.output_dir): sys.exit(1)

    # --- Load Program Definitions ---
    program_definitions = load_program_definitions(args.config_file)
    if not program_definitions:
        sys.exit(1)

    # --- Prepare Program Configurations (Now uses all definitions) ---
    programs_to_run = prepare_program_configurations(program_definitions)

    if not programs_to_run:
        print("\nERROR: No valid programs were successfully configured from the JSON file. Exiting.")
        sys.exit(1)

    print("\n--- Final Program Instances to Run ---")
    if programs_to_run:
        for prog in programs_to_run:
            print(f"  Name: {prog['name']}, Build: {prog['build_type']}, "
                  f"Src: {prog['src_dir']}, "
                  f"RunArgs: {prog['run_args']}, CompileDefs: {prog.get('compile_defs', [])}")
    else:
        print("  None.") # Should not happen due to check above, but safe


    # --- Determine Flag Configurations ---
    flag_configs = {}
    print(f"\n--- Determining Flag Configurations (Mode: {args.flags_mode}) ---")
    if args.flags_mode == 'levels':
        print(f"INFO: Using standard optimization levels: {config.DEFAULT_OPTIMIZATION_LEVELS}")
        for level in config.DEFAULT_OPTIMIZATION_LEVELS: flag_configs[level] = [f"-{level}"]
    elif args.flags_mode == 'o2_vs_o3_diff':
        print("INFO: Generating flag configurations for O2 vs O3 comparison (individual flags).")
        flag_configs = utils.get_o2_o3_flag_configs()
        print(f"INFO: Generated {len(flag_configs)} configurations for O2 vs O3 diff.")
    # --- ADDED ELIF ---
    elif args.flags_mode == 'o2_to_o3_cumulative':
        print("INFO: Generating flag configurations for O2 to O3 CUMULATIVE addition.")
        flag_configs = utils.get_o2_to_o3_cumulative_configs()
        print(f"INFO: Generated {len(flag_configs)} cumulative configurations.")
    # --- END ADDED ELIF ---
    else: # Should be caught by argparse choices, but defensive check
        parser.error(f"Invalid flags-mode: {args.flags_mode}")
    print(f"INFO: Total flag configurations to test per program instance: {len(flag_configs)}")

    # --- Execute Actions ---
    build_results = {}
    jobs_info = {}
    analysis_df = None
    plot_paths = {}

    # Build Stage
    if args.action in ['full-run', 'build'] and not getattr(args, 'skip_build', False):
        build_results = build.build_configurations(
            programs_to_run, flag_configs, args.output_dir,
            getattr(args, 'force_rebuild', False)
        )
        # Check build results...
        successful_builds = sum(1 for path in build_results.values() if path is not None)
        if successful_builds == 0 and len(build_results) > 0:
             print("ERROR: All builds failed. Check logs. Aborting further steps.")
             sys.exit(1)
        elif successful_builds < len(build_results):
             print("WARNING: Some builds failed. Proceeding with successful builds only.")


    # Run Stage
    if args.action in ['full-run', 'run'] and not getattr(args, 'skip_run', False):
        # Populate build_results if build was skipped...
        if not build_results and (args.action == 'run' or getattr(args, 'skip_build', False)):
             print("INFO: Build stage skipped, attempting to find existing executables for run stage.")
             build_results = build.find_existing_builds(
                  programs_to_run, flag_configs, args.output_dir
             )
             if not build_results:
                  print("ERROR: No existing executables found and build was skipped. Cannot run.")
                  sys.exit(1)

        jobs_info = slurm.run_slurm_benchmarks(
            programs_to_run, flag_configs, build_results, args.num_runs,
            args.output_dir, getattr(args, 'submit', False)
        )

    # Analyze Stage
    if args.action in ['full-run', 'analyze'] and not getattr(args, 'skip_analyze', False):
        # Wait for jobs if requested... (Add wait logic if needed)
        analysis_df = analyze.analyze_log_files(
            programs_to_run, flag_configs, args.num_runs, args.output_dir
        )

    # Report Stage
    if args.action in ['full-run', 'report'] and not getattr(args, 'skip_report', False):
        # Load existing results if needed...
        if analysis_df is None and (args.action == 'report' or getattr(args, 'skip_analyze', False)):
             results_csv_path = args.results_csv or args.output_dir / config.RESULTS_SUBDIR / "benchmark_results_raw.csv"
             if results_csv_path.is_file():
                  print(f"INFO: Loading existing analysis results from: {results_csv_path}")
                  try:
                       analysis_df = pd.read_csv(results_csv_path)
                       # Convert RawTimes back to list if needed (it's often stored as string)
                       if 'RawTimes' in analysis_df.columns:
                            analysis_df['RawTimes'] = analysis_df['RawTimes'].apply(lambda x: eval(x) if isinstance(x, str) else x)
                       # Convert Statuses back to list
                       if 'Statuses' in analysis_df.columns:
                            analysis_df['Statuses'] = analysis_df['Statuses'].apply(lambda x: eval(x) if isinstance(x, str) else x)
                       # Ensure FlagsID is categorical if applicable
                       if all(fid in config.DEFAULT_OPTIMIZATION_LEVELS for fid in analysis_df['FlagsID'].unique()):
                            opt_order = pd.CategoricalDtype(config.DEFAULT_OPTIMIZATION_LEVELS, ordered=True)
                            analysis_df['FlagsID'] = analysis_df['FlagsID'].astype(opt_order)
                       analysis_df = analysis_df.sort_values(by=['Program', 'FlagsID'])

                  except Exception as e:
                       print(f"ERROR: Failed to load or parse existing results CSV {results_csv_path}: {e}")
                       analysis_df = None
             else:
                  print(f"INFO: Analyze stage skipped and no existing results file found at {results_csv_path}. Cannot generate report.")


        if analysis_df is not None:
            plot_paths = report.create_plots(analysis_df, args.output_dir)
            # Get the list of program instance names that were actually analyzed
            analyzed_program_names = sorted(analysis_df['Program'].unique())
            report.generate_markdown_report(
                analysis_df, plot_paths,
                analyzed_program_names, # Pass names from analysis df
                flag_configs, args.output_dir
            )
        else:
             print("INFO: No analysis data available. Skipping report generation.")


    print("\n=============================================")
    print("=== Benchmark Script Finished ===")
    print("=============================================")


if __name__ == "__main__":
    main()
