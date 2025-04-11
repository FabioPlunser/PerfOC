# utils.py
import os
import subprocess
import shutil
from pathlib import Path
import hashlib
import re

import config # Import static config

def run_command(cmd, cwd=None, env=None, check=True, shell=False, capture=True, verbose=True):
    """Runs a command, prints output, and checks return code."""
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    if verbose:
        print(f"INFO: Running: {cmd_str} in {cwd or os.getcwd()}")
    try:
        result = subprocess.run(
            cmd, capture_output=capture, text=True, cwd=cwd, env=env,
            check=check, shell=shell,
        )
        # Less verbose debug logging
        # if capture and verbose:
        #     if result.stdout: print(f"DEBUG STDOUT:\n{result.stdout.strip()}")
        #     if result.stderr: print(f"DEBUG STDERR:\n{result.stderr.strip()}")
        if verbose:
            print(f"INFO: Command finished with exit code {result.returncode}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}")
        if capture: # Only print captured output on error
            if e.stdout: print(f"ERROR STDOUT:\n{e.stdout.strip()}")
            if e.stderr: print(f"ERROR STDERR:\n{e.stderr.strip()}")
        if check: raise
        return e
    except Exception as e:
        print(f"ERROR: An unexpected error occurred running command: {e}")
        raise

def load_modules(verbose=True):
    """Loads the required environment modules."""
    if verbose: print("\n--- Loading Environment Modules ---")
    try:
        if verbose: print("INFO: Running 'module purge'")
        run_command("module purge", shell=True, check=True, capture=False, verbose=verbose)
        for mod in config.MODULES_TO_LOAD:
            if verbose: print(f"INFO: Loading module: {mod}")
            run_command(f"module load {mod}", shell=True, check=True, capture=False, verbose=verbose)
        if verbose:
            print("INFO: Running 'module list' to verify:")
            run_command("module list", shell=True, check=False, capture=False, verbose=verbose)
            print("INFO: Modules loaded successfully.")
            print("INFO: Verifying essential tools (gcc, g++, cmake, ninja)...")
        tools_ok = True
        for tool in [config.CC, config.CXX, "cmake", "ninja"]:
            if not shutil.which(tool):
                print(f"  ERROR: Command '{tool}' not found in PATH after loading modules.")
                tools_ok = False
        if not tools_ok:
             print("ERROR: Not all required tools found. Check module names and availability.")
             return False
        if verbose: print("INFO: Essential tools verified.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to load modules: {e}")
        return False

def ensure_output_dirs(base_output_dir):
    """Creates necessary output directories."""
    print("INFO: Ensuring output directories exist...")
    dirs_to_create = [
        base_output_dir / config.BUILD_SUBDIR,
        base_output_dir / config.SLURM_SCRIPTS_SUBDIR,
        base_output_dir / config.SLURM_LOGS_SUBDIR,
        base_output_dir / config.RESULTS_SUBDIR,
        base_output_dir / config.RESULTS_SUBDIR / config.PLOTS_SUBDIR,
    ]
    all_created = True
    for d in dirs_to_create:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"ERROR: Could not create directory {d}: {e}")
            all_created = False
    if all_created:
        print("INFO: Output directories ensured.")
    return all_created

def sanitize_flags(flags_string):
    """Creates a safe filesystem identifier from a flags string."""
    if not flags_string: return "no_flags"
    # Remove leading/trailing whitespace, replace spaces with underscores
    sanitized = flags_string.strip().replace(" ", "_")
    # Remove potentially problematic characters (keep alphanumeric, underscore, hyphen, plus, equals)
    sanitized = re.sub(r'[^\w\-+=]', '', sanitized)
    # Handle very long strings (e.g., hash them)
    if len(sanitized) > 50:
        hasher = hashlib.sha1(flags_string.encode())
        sanitized = "flags_hash_" + hasher.hexdigest()[:10]
    return sanitized if sanitized else "invalid_flags"

def get_o2_o3_flag_configs():
    """
    Generates flag configurations for Exercise B (INDIVIDUAL flags added to O2).
    """
    # Base O2 config
    configs = {"O2_baseline": ["-O2"]}
    # Add configs for each O3 flag toggled on top of O2
    for flag, (o2_val, o3_val) in config.O2_O3_DIFF_FLAGS.items():
        # Logic to handle simple flags and flags with =value
        if o2_val == 0 and o3_val == 1: # Flag is off in O2, on in O3
            flag_name_option = f"-{flag}" # e.g., -fipa-cp-clone or -fvect-cost-model=dynamic
            # Sanitize flag name for the config key
            sanitized_flag_part = flag.replace('-', '_').replace('=', '_')
            config_name = f"O2_plus_{sanitized_flag_part}" # e.g., O2_plus_fipa_cp_clone
            configs[config_name] = ["-O2", flag_name_option] # List of flags: [-O2, -the-specific-flag]
        # Add more logic here if flags can be *disabled* in O3 vs O2, etc.
    # Add O3 baseline for comparison
    configs["O3_baseline"] = ["-O3"]
    return configs

def get_o2_to_o3_cumulative_configs():
    """
    Generates flag configurations starting with -O2 and cumulatively
    adding flags from the O2-O3 diff list in alphabetical order.
    """
    configs = {"O2_baseline": ["-O2"]}
    current_flags = ["-O2"]

    # Get the list of flags that are different (enabled in O3, disabled in O2)
    o3_specific_flags = []
    for flag, (o2_val, o3_val) in config.O2_O3_DIFF_FLAGS.items():
        if o2_val == 0 and o3_val == 1:
            o3_specific_flags.append(flag)
        # Add logic here if other differences exist (e.g., flags disabled in O3)

    # Add flags cumulatively in a defined order (alphabetical)
    sorted_flags = sorted(o3_specific_flags)

    for i, flag_name in enumerate(sorted_flags):
        flag_option = f"-{flag_name}"
        current_flags.append(flag_option)

        # Create a meaningful name for the configuration step
        sanitized_flag_part = flag_name.replace('-', '_').replace('=', '_')
        config_name = f"O2_cumul_{i+1}_{sanitized_flag_part}"

        # Store a COPY of the current flag list for this configuration
        configs[config_name] = current_flags.copy()
        print(f"DEBUG: Generated cumulative config '{config_name}': {' '.join(configs[config_name])}")


    # Add O3 baseline for comparison (should be similar to the last cumulative step)
    configs["O3_baseline"] = ["-O3"]
    print(f"DEBUG: Added O3 baseline config: {' '.join(configs['O3_baseline'])}")

    return configs