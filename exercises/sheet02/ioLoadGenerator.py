#!/usr/bin/env python3

import os
import subprocess
import argparse
import threading
import random
import time
import signal
import sys
from pathlib import Path
import tempfile
import shutil
import psutil


class IOLoadGenerator:
    def __init__(self, target_dir, intensity=3, file_size_mb=10, buffer_size_mb=1):
        """
        Initialize the I/O load generator.

        Args:
            target_dir: Directory to use for I/O operations
            intensity: Number of files to process simultaneously
            file_size_mb: Size of each file in MB
            buffer_size_mb: Size of buffer for read/write operations in MB
        """
        self.target_dir = Path(target_dir)
        self.intensity = intensity
        self.file_size = file_size_mb * 1024 * 1024  # Convert to bytes
        self.buffer_size = buffer_size_mb * 1024 * 1024  # Convert to bytes
        self.running = False
        self.threads = []
        self.stats = {
            "bytes_written": 0,
            "bytes_read": 0,
            "files_created": 0,
            "files_deleted": 0,
            "start_time": None,
            "end_time": None,
        }

    def start(self):
        """Start the I/O load generator with specified number of threads"""
        self.running = True
        self.stats["start_time"] = time.time()

        # Create target directory if it doesn't exist
        os.makedirs(self.target_dir, exist_ok=True)

        # Start worker threads
        for i in range(self.intensity):
            thread = threading.Thread(target=self._generate_load, args=(i,))
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

        print(
            f"I/O load generator started with {self.intensity} threads in {self.target_dir}"
        )

    def stop(self):
        """Stop the I/O load generator and clean up"""
        self.running = False

        # Wait for all threads to finish
        for thread in self.threads:
            thread.join(timeout=2)

        self.stats["end_time"] = time.time()
        self._print_stats()

        # Clean up any remaining files
        self._cleanup()

        print("I/O load generator stopped")

    def _generate_load(self, thread_id):
        """Generate I/O load by creating, writing, reading, and deleting files"""
        buffer = b"x" * self.buffer_size

        while self.running:
            # Create a unique filename
            filename = (
                self.target_dir / f"io_load_{thread_id}_{random.randint(1, 10000)}.dat"
            )

            try:
                # Create and write to file
                with open(filename, "wb") as f:
                    bytes_written = 0
                    for _ in range(0, self.file_size, self.buffer_size):
                        if not self.running:
                            break
                        f.write(buffer)
                        f.flush()
                        os.fsync(f.fileno())
                        bytes_written += self.buffer_size

                self.stats["bytes_written"] += bytes_written
                self.stats["files_created"] += 1

                # Read the file
                if self.running:
                    with open(filename, "rb") as f:
                        bytes_read = 0
                        while self.running:
                            data = f.read(self.buffer_size)
                            if not data:
                                break
                            bytes_read += len(data)

                    self.stats["bytes_read"] += bytes_read

                # Delete the file
                if os.path.exists(filename):
                    os.unlink(filename)
                    self.stats["files_deleted"] += 1

            except Exception as e:
                print(f"Thread {thread_id} error: {e}")

            # Small sleep to prevent complete system overload
            if self.running:
                time.sleep(0.1)

    def _cleanup(self):
        """Clean up any remaining files"""
        for file in self.target_dir.glob("io_load_*.dat"):
            try:
                os.unlink(file)
                self.stats["files_deleted"] += 1
            except:
                pass

    def _print_stats(self):
        """Print statistics about the I/O operations performed"""
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]

            print("\nI/O Load Generator Statistics:")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Files created: {self.stats['files_created']}")
            print(f"Files deleted: {self.stats['files_deleted']}")

            mb_written = self.stats["bytes_written"] / (1024 * 1024)
            mb_read = self.stats["bytes_read"] / (1024 * 1024)

            print(f"Data written: {mb_written:.2f} MB ({mb_written/duration:.2f} MB/s)")
            print(f"Data read: {mb_read:.2f} MB ({mb_read/duration:.2f} MB/s)")
            print(
                f"Total I/O: {(mb_written + mb_read):.2f} MB ({(mb_written + mb_read)/duration:.2f} MB/s)"
            )


def monitor_system_io(interval=1.0, duration=None):
    """
    Monitor system I/O statistics.

    Args:
        interval: Sampling interval in seconds
        duration: Total monitoring duration in seconds (None for indefinite)
    """
    print("Starting I/O monitoring...")
    print("Time\tRead MB/s\tWrite MB/s\tRead IOPS\tWrite IOPS")

    start_time = time.time()
    last_disk_io = psutil.disk_io_counters()
    last_time = start_time

    try:
        while True:
            time.sleep(interval)

            current_time = time.time()
            current_disk_io = psutil.disk_io_counters()

            # Calculate rates
            time_delta = current_time - last_time

            read_bytes = current_disk_io.read_bytes - last_disk_io.read_bytes
            write_bytes = current_disk_io.write_bytes - last_disk_io.write_bytes
            read_count = current_disk_io.read_count - last_disk_io.read_count
            write_count = current_disk_io.write_count - last_disk_io.write_count

            read_mb_s = read_bytes / time_delta / (1024 * 1024)
            write_mb_s = write_bytes / time_delta / (1024 * 1024)
            read_iops = read_count / time_delta
            write_iops = write_count / time_delta

            elapsed = current_time - start_time
            print(
                f"{elapsed:.1f}s\t{read_mb_s:.2f}\t{write_mb_s:.2f}\t{read_iops:.1f}\t{write_iops:.1f}"
            )

            last_disk_io = current_disk_io
            last_time = current_time

            # Check if we've reached the duration
            if duration and (current_time - start_time) >= duration:
                break

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")


def run_benchmark_with_io_load(benchmark_cmd, target_dir, intensity=3, file_size_mb=10):
    """
    Run a benchmark command with I/O load.

    Args:
        benchmark_cmd: Command to run as the benchmark
        target_dir: Directory to use for I/O operations
        intensity: I/O load intensity (number of threads)
        file_size_mb: Size of each file in MB
    """
    print(f"Running benchmark with I/O load (intensity={intensity})")
    print(f"Benchmark command: {benchmark_cmd}")

    # Start I/O load generator
    io_load = IOLoadGenerator(target_dir, intensity, file_size_mb)
    io_load.start()

    try:
        # Wait a moment for I/O load to stabilize
        time.sleep(2)

        # Run the benchmark
        start_time = time.time()
        result = subprocess.run(
            benchmark_cmd, shell=True, capture_output=True, text=True
        )
        end_time = time.time()

        # Print benchmark results
        print("\nBenchmark Results:")
        print(f"Duration: {end_time - start_time:.2f} seconds")
        print(f"Exit code: {result.returncode}")

        if result.stdout:
            print("\nStandard output:")
            print(result.stdout)

        if result.stderr:
            print("\nStandard error:")
            print(result.stderr)

        return result

    finally:
        # Stop I/O load generator
        io_load.stop()


def main():
    parser = argparse.ArgumentParser(description="I/O Load Generator for Benchmarking")

    # Create subparsers for different modes
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # Parser for 'generate' mode
    gen_parser = subparsers.add_parser("generate", help="Generate I/O load")
    gen_parser.add_argument(
        "--dir",
        type=str,
        default=tempfile.gettempdir(),
        help="Target directory for I/O operations",
    )
    gen_parser.add_argument(
        "--intensity",
        type=int,
        default=3,
        help="I/O load intensity (number of threads)",
    )
    gen_parser.add_argument(
        "--file-size", type=int, default=10, help="Size of each file in MB"
    )
    gen_parser.add_argument(
        "--duration", type=int, default=30, help="Duration to run in seconds"
    )

    # Parser for 'monitor' mode
    mon_parser = subparsers.add_parser("monitor", help="Monitor system I/O")
    mon_parser.add_argument(
        "--interval", type=float, default=1.0, help="Sampling interval in seconds"
    )
    mon_parser.add_argument(
        "--duration", type=int, default=None, help="Monitoring duration in seconds"
    )

    # Parser for 'benchmark' mode
    bench_parser = subparsers.add_parser(
        "benchmark", help="Run benchmark with I/O load"
    )
    bench_parser.add_argument(
        "--dir",
        type=str,
        default=tempfile.gettempdir(),
        help="Target directory for I/O operations",
    )
    bench_parser.add_argument(
        "--intensity",
        type=int,
        default=3,
        help="I/O load intensity (number of threads)",
    )
    bench_parser.add_argument(
        "--file-size", type=int, default=10, help="Size of each file in MB"
    )
    bench_parser.add_argument(
        "command", type=str, nargs="+", help="Benchmark command to run"
    )

    args = parser.parse_args()

    # Handle different modes
    if args.mode == "generate":
        print(f"Generating I/O load in {args.dir} for {args.duration} seconds...")
        io_load = IOLoadGenerator(args.dir, args.intensity, args.file_size)
        io_load.start()

        # Set up signal handler for clean shutdown
        def signal_handler(sig, frame):
            print("\nReceived interrupt, shutting down...")
            io_load.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            time.sleep(args.duration)
        finally:
            io_load.stop()

    elif args.mode == "monitor":
        monitor_system_io(args.interval, args.duration)

    elif args.mode == "benchmark":
        benchmark_cmd = " ".join(args.command)
        run_benchmark_with_io_load(
            benchmark_cmd, args.dir, args.intensity, args.file_size
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
