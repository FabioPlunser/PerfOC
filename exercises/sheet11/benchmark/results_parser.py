import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_elapsed_time(time_str: str) -> float | None:
    """Parses elapsed time string (e.g., 0.00, 0:00.00, 1:02:03.04) into seconds."""
    if not time_str:
        return None

    # Simpler case: just seconds
    match_simple = re.fullmatch(r"(\d+\.\d+)", time_str)
    if match_simple:
        return float(match_simple.group(1))

    # h:mm:ss.ss or mm:ss.ss or ss.ss (within context of "Elapsed...")
    # The pattern tries to capture optional hours, optional minutes, and seconds.
    # Example: "Elapsed (wall clock) time (h:mm:ss or m:ss): 1:02:03.04"
    # Example: "Elapsed (wall clock) time (h:mm:ss or m:ss): 02:03.04"
    # Example: "Elapsed (wall clock) time (h:mm:ss or m:ss): 03.04" -> this case is covered by simple match

    parts = time_str.split(":")
    try:
        if len(parts) == 3:  # h:mm:ss.ss
            h = int(parts[0])
            m = int(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:  # mm:ss.ss
            m = int(parts[0])
            s = float(parts[1])
            return m * 60 + s
        elif (
            len(parts) == 1
        ):  # ss.ss (already handled by simple match, but as fallback)
            return float(parts[0])
    except ValueError:
        logger.warning(f"Could not parse time string: {time_str}")
        return None
    return None


def parse_time_output(log_content: str) -> dict:
    """Parses the verbose output of /usr/bin/time."""
    data = {}
    patterns = {
        "user_time_s": r"User time \(seconds\):\s*([\d\.]+)",
        "system_time_s": r"System time \(seconds\):\s*([\d\.]+)",
        "elapsed_time_str": r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([\d:\.]+)",
        "max_rss_kb": r"Maximum resident set size \(kbytes\):\s*(\d+)",
        "avg_rss_kb": r"Average resident set size \(kbytes\):\s*(\d+)",
        "cpu_percent": r"Percent of CPU this job got:\s*([\d\.]+)%",
        "page_faults_major": r"Major page faults:\s*(\d+)",
        "page_faults_minor": r"Minor page faults:\s*(\d+)",
        "swaps": r"Swaps:\s*(\d+)",
        "context_switches_voluntary": r"Voluntary context switches:\s*(\d+)",
        "context_switches_involuntary": r"Involuntary context switches:\s*(\d+)",
        "internal_time_ns": r"Internal_Time_ns:\s*(\d+)",
        "internal_time_s_precise": r"Internal_Time_s:\s*([\d\.]+)"
    }


    for key, pattern in patterns.items():
        match = re.search(pattern, log_content)
        if match:
            value_str = match.group(1)
            if key == "internal_time_ns":
                data[key] = int(value_str) 
            elif key == "internal_time_s_precise":
                data[key] = float(value_str)
            elif key == "elapsed_time_str":
                data["elapsed_time_s"] = parse_elapsed_time(value_str)
                data[key] = value_str  
            elif key in [
                "max_rss_kb",
                "avg_rss_kb",
                "page_faults_major",
                "page_faults_minor",
                "swaps",
                "context_switches_voluntary",
                "context_switches_involuntary",
            ]:
                data[key] = int(value_str)
            else:  
                data[key] = float(value_str)
        else:
            data[key] = None  

    if data.get("max_rss_kb") is not None:
        data["max_rss_mb"] = data["max_rss_kb"] / 1024.0
    else:
        data["max_rss_mb"] = None

    # Extract Delannoy result and verification
    delannoy_match = re.search(
        r"Delannoy(?:_memo|_tabulate)?\(\d+, \d+\) = (\d+)", log_content
    )
    if delannoy_match:
        data["delannoy_result"] = int(delannoy_match.group(1))

    verification_match = re.search(r"Verification: (OK|ERR.*|N/A.*)", log_content)
    if verification_match:
        data["verification_status"] = verification_match.group(1).strip()

    if "ERROR" in log_content.upper() or "SEGMENTATION FAULT" in log_content.upper():
        data["error_detected"] = True
    else:
        data["error_detected"] = False

    return data


def parse_single_log(
    log_path: Path, program_name: str, n_value: int, repetition: int
) -> dict | None:
    """Parses a single SLURM log file."""
    if not log_path.exists():
        logger.warning(f"Log file not found: {log_path}")
        return None
    try:
        with open(log_path, "r") as f:
            content = f.read()

        parsed_data = parse_time_output(content)
        parsed_data["program"] = program_name
        parsed_data["n_value"] = n_value
        parsed_data["repetition"] = repetition
        parsed_data["log_file"] = log_path.name

        # Check if essential data is missing (e.g., time command didn't run or output was minimal)
        if (
            parsed_data.get("user_time_s") is None
            and parsed_data.get("elapsed_time_s") is None
        ):
            logger.warning(
                f"Essential time data missing in {log_path.name}. Log content might be incomplete or errored before time command."
            )
            parsed_data["error_detected"] = True  # Mark as error if time is missing

        return parsed_data
    except Exception as e:
        logger.error(f"Failed to parse log file {log_path.name}: {e}", exc_info=True)
        return {
            "program": program_name,
            "n_value": n_value,
            "repetition": repetition,
            "log_file": log_path.name,
            "error_detected": True,
            "parse_error": str(e),
        }
