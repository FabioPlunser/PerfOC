# build.py
import os
import shutil
from pathlib import Path
import stat

import config
from utils import run_command, sanitize_flags

def build_program(prog_config, flags_list, base_output_dir, force_rebuild=False):
    """
    Builds a single program with a specific list of optimization flags.

    Args:
        prog_config (dict): Configuration dictionary for the program instance.
        flags_list (list): List of flag strings (e.g., ["-O2", "-fflag"]).
        base_output_dir (Path): Base directory for all outputs.
        force_rebuild (bool): If True, delete existing build dir first.

    Returns:
        Path or None: Path to the built executable if successful, None otherwise.
    """
    prog_name = prog_config['name'] # Use the specific instance name
    # Create a unique identifier for the flags combination
    flags_string = " ".join(sorted(flags_list)) # Sort for consistency
    flags_id = sanitize_flags(flags_string) # Use helper from utils

    build_dir = base_output_dir / config.BUILD_SUBDIR / prog_name / flags_id
    # Use the absolute src_dir from the prog_config instance
    src_dir = prog_config['src_dir'].resolve()
    build_type = prog_config['build_type']
    exe_path = build_dir / prog_config['exe_subdir'] / prog_config['exe_name']

    print(f"\n--- Building {prog_name} with flags '{flags_string}' (ID: {flags_id}) ---")
    print(f"DEBUG Source dir: {src_dir}")
    print(f"DEBUG Build dir: {build_dir}")

    if build_dir.exists():
        if force_rebuild:
            print(f"INFO: Force rebuild requested. Removing existing build directory: {build_dir}")
            shutil.rmtree(build_dir)
        elif exe_path.is_file():
             print(f"INFO: Executable {exe_path.name} already exists. Skipping build (use --force-rebuild to override).")
             return exe_path
        else:
             print(f"WARNING: Build dir exists but executable {exe_path.name} is missing. Rebuilding.")
             shutil.rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)

    try:
        env = os.environ.copy()
        # Combine all flags into a single string for CMake/GCC
        full_flags_string = flags_string # Already joined and sorted

        # --- Get compile_defs from the config ---
        # Needed for both CMake and GCC builds potentially
        compile_defs = prog_config.get('compile_defs', [])

        if build_type == 'cmake':
            print("DEBUG Using CMake build type...")
            # Get base flags from config and append the optimization/specific flags
            base_c_flags = prog_config.get("cmake_base_c_flags", "")
            # --- Combine opt flags, base flags, and compile defs for C ---
            final_c_flags = f"{full_flags_string} {base_c_flags} {' '.join(compile_defs)}".strip()

            base_cxx_flags = prog_config.get("cmake_base_cxx_flags", "")
            # --- Combine opt flags, base flags, and compile defs for C++ ---
            final_cxx_flags = f"{full_flags_string} {base_cxx_flags} {' '.join(compile_defs)}".strip()


            cmake_args = [
                "cmake", str(src_dir), "-G", "Ninja",
                f"-DCMAKE_BUILD_TYPE=Release", # Keep Release type
                # Quote flags carefully for shell interpretation within CMake
                f"-DCMAKE_C_FLAGS='{final_c_flags}'",
                f"-DCMAKE_CXX_FLAGS='{final_cxx_flags}'",
            ]
            print(f"DEBUG Running CMake: {' '.join(cmake_args)}")
            # Use shell=True if flags contain spaces/quotes that need shell parsing
            # Be cautious with shell=True and ensure flags are properly escaped if needed
            run_command(cmake_args, cwd=build_dir, env=env, check=True, verbose=False) # Less verbose

            ninja_cmd = ["ninja"]
            # Use the potentially updated cmake_target from the prog_config instance
            cmake_target = prog_config.get('cmake_target')
            if cmake_target: ninja_cmd.append(cmake_target)
            print(f"DEBUG Running Ninja: {' '.join(ninja_cmd)}")
            run_command(ninja_cmd, cwd=build_dir, env=env, check=True, verbose=False) # Less verbose

        elif build_type == 'gcc':
            print("DEBUG Using direct GCC build type...")
            lang = prog_config.get('lang', 'c')
            compiler = config.CXX if lang == 'c++' else config.CC

            source_files_rel = prog_config.get('source_files', [])
            source_files_abs = [str(src_dir / sf) for sf in source_files_rel]
            # Basic check for file existence
            for sf_abs in source_files_abs:
                 if not Path(sf_abs).is_file(): print(f"WARNING: Source file not found: {sf_abs}")

            include_dirs_rel = prog_config.get('include_dirs', [])
            # Include src_dir itself and specified include dirs relative to src_dir
            include_flags = [f"-I{src_dir / idir}" for idir in include_dirs_rel] + [f"-I{src_dir}"]
            link_libs = prog_config.get('link_libs', [])

            # Split the combined flags string back into a list for the command
            flags_for_cmd = full_flags_string.split()

            # Calculate the output path RELATIVE to the build_dir
            relative_exe_path = Path(prog_config['exe_subdir']) / prog_config['exe_name']
            # Ensure the parent directory for the relative path exists within build_dir
            (build_dir / relative_exe_path.parent).mkdir(parents=True, exist_ok=True)

            # --- Construct the compile command including compile_defs ---
            compile_cmd = ([compiler] + flags_for_cmd + compile_defs +
                           ["-o", str(relative_exe_path)] +
                           include_flags +
                           source_files_abs + link_libs)
            print(f"DEBUG Compiler command: {' '.join(compile_cmd)}")
            # Run the command with cwd=build_dir
            run_command(compile_cmd, cwd=build_dir, check=True, verbose=False) # Less verbose
        else:
            print(f"ERROR: Unknown build type '{build_type}' for {prog_name}")
            return None

        # Check the original full exe_path for existence after build
        if exe_path.is_file():
            # Ensure executable permission using stat
            exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC)
            print(f"INFO: Build successful for {prog_name} with flags ID {flags_id}")
            return exe_path
        else:
            print(f"ERROR: Executable not created after build: {exe_path}")
            return None
    except Exception as e:
        print(f"ERROR: Build FAILED for {prog_name} with flags ID {flags_id}: {e}")
        # Optionally print traceback for more detail
        # import traceback
        # traceback.print_exc()
        if build_dir.exists():
             try: shutil.rmtree(build_dir); print(f"DEBUG Cleaned up failed build directory: {build_dir}")
             except OSError as rm_err: print(f"WARNING: Could not remove failed build directory {build_dir}: {rm_err}")
        return None

# --- build_configurations and find_existing_builds remain the same ---
# (Make sure they are using the code from the previous correct version)
def build_configurations(programs_to_run, flag_configs, base_output_dir, force_rebuild=False):
    """Builds all selected programs for all specified flag configurations."""
    print("\n--- Starting Batch Build Process ---")
    build_results = {} # Store { (prog_name, flags_id): exe_path or None }
    total_builds = 0
    success_count = 0
    fail_count = 0
    skip_count = 0 # Track skipped builds (already exists)

    if not programs_to_run:
        print("INFO: No programs selected for building.")
        return {}

    # Calculate total expected builds accurately
    total_builds = len(programs_to_run) * len(flag_configs)
    print(f"INFO: Planning to build {len(programs_to_run)} program instances with {len(flag_configs)} flag configurations each (Total: {total_builds} builds).")

    for prog in programs_to_run:
        prog_name = prog['name'] # Use the instance name
        for flags_id, flags_list in flag_configs.items():
            # Pass the specific prog instance config to build_program
            exe_path = build_program(prog, flags_list, base_output_dir, force_rebuild)
            # Use the sanitized flags_id generated within build_program for the key
            # Re-generate it here for consistency in the results dictionary key
            flags_string = " ".join(sorted(flags_list))
            sanitized_flags_id = sanitize_flags(flags_string)
            build_results[(prog_name, sanitized_flags_id)] = exe_path # Use sanitized ID as key

            if exe_path:
                # This count includes successful builds and skipped existing builds
                 success_count += 1
            else:
                fail_count += 1
                # Decide if failure for one config should stop others for this program
                # break # Uncomment to stop building this program after first failure

    print("\n--- Batch Build Summary ---")
    print(f"Total build attempts planned: {total_builds}")
    # Success count might include builds that were skipped because they existed
    print(f"Successful builds (or existing executables found): {success_count}")
    print(f"Failed builds: {fail_count}")

    if fail_count > 0:
        print("WARNING: One or more builds failed. Check logs above.")

    return build_results # Return map of build attempts to results


def find_existing_builds(programs_to_run, flag_configs, base_output_dir):
    """Checks for existing executables without attempting to build."""
    print("\n--- Checking for Existing Builds ---")
    build_results = {}
    found_count = 0
    missing_count = 0

    for prog in programs_to_run:
        prog_name = prog['name'] # Instance name
        for flags_id, flags_list in flag_configs.items():
            # Reconstruct the expected path using the sanitized ID
            flags_string = " ".join(sorted(flags_list))
            sanitized_flags_id = sanitize_flags(flags_string) # Ensure consistent ID
            build_dir = base_output_dir / config.BUILD_SUBDIR / prog_name / sanitized_flags_id
            exe_path = build_dir / prog['exe_subdir'] / prog['exe_name']

            if exe_path.is_file():
                # print(f"DEBUG Found existing executable: {exe_path}")
                build_results[(prog_name, flags_id)] = exe_path # Use original flags_id as key
                found_count += 1
            else:
                # print(f"DEBUG Missing executable: {exe_path}")
                build_results[(prog_name, flags_id)] = None # Use original flags_id as key
                missing_count += 1

    print(f"INFO: Found {found_count} existing executables.")
    if missing_count > 0:
        print(f"INFO: Did not find {missing_count} expected executables.")
    return build_results
