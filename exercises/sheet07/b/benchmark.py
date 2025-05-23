import subprocess
import time
import matplotlib.pyplot as plt
import numpy as np
import os

# Compile both versions
def compile_programs():
    print("Compiling original version...")
    subprocess.run("gcc -o malloctest_original malloctest.c -pthread", shell=True, check=True)
    
    print("Compiling bump allocator version...")
    subprocess.run("gcc -o malloctest_bump bump_malloctest.c -pthread", shell=True, check=True)
    
    print("Compilation complete.")

# Run a program and measure its execution time
def run_program(program, args, run_number):
    cmd = f"./{program} {args}"
    print(f"Running {program} (run {run_number+1}): {cmd}")
    
    start_time = time.time()
    subprocess.run(cmd, shell=True, check=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.2f} seconds")
    return execution_time

# Run benchmark
def run_benchmark(args="1 500 1000000 10 1000", runs=1):
    results = {
        "Original Allocator": [],
        "Bump Allocator": []
    }
    
    # Run original version
    for i in range(runs):
        time_taken = run_program("malloctest_original", args, i)
        results["Original Allocator"].append(time_taken)
    
    # Run bump allocator version
    for i in range(runs):
        time_taken = run_program("malloctest_bump", args, i)
        results["Bump Allocator"].append(time_taken)
    
    return results

# Create a bar chart comparing the results
def create_plot(results):
    allocators = list(results.keys())
    avg_times = [np.mean(results[allocator]) for allocator in allocators]
    std_times = [np.std(results[allocator]) for allocator in allocators]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Bar positions
    x_pos = np.arange(len(allocators))
    
    # Create bars
    bars = ax.bar(x_pos, avg_times, yerr=std_times, align='center', 
                  alpha=0.7, ecolor='black', capsize=10)
    
    # Add values on top of bars
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + std_times[i] + 0.1,
                f'{avg_times[i]:.2f}s', ha='center', va='bottom')
    
    # Customize chart
    ax.set_ylabel('Execution Time (seconds)')
    ax.set_title('Memory Allocator Performance Comparison')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(allocators)
    
    # Add individual run data points
    for i, allocator in enumerate(allocators):
        x = np.random.normal(i, 0.05, size=len(results[allocator]))
        ax.plot(x, results[allocator], 'o', color='black', alpha=0.6)
    
    # Calculate speedup
    if avg_times[0] > 0:
        speedup = avg_times[0] / avg_times[1]
        ax.text(0.5, 0.95, f'Speedup: {speedup:.2f}x', 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=12, 
                bbox=dict(facecolor='white', alpha=0.8))
    
    # Save and show plot
    plt.tight_layout()
    plt.savefig('allocator_comparison.png')
    plt.show()
    
    print(f"Plot saved as allocator_comparison.png")

# Print detailed results
def print_results(results):
    print("\n--- BENCHMARK RESULTS ---")
    for allocator, times in results.items():
        avg_time = np.mean(times)
        std_time = np.std(times)
        print(f"{allocator}:")
        print(f"  Individual runs: {', '.join([f'{t:.2f}s' for t in times])}")
        print(f"  Average time: {avg_time:.2f}s ± {std_time:.2f}s")
    
    # Calculate speedup
    orig_avg = np.mean(results["Original Allocator"])
    bump_avg = np.mean(results["Bump Allocator"])
    if bump_avg > 0:
        speedup = orig_avg / bump_avg
        print(f"\nSpeedup: {speedup:.2f}x")

# Main function
def main():
    # Check if source files exist
    if not os.path.exists("malloctest.c"):
        print("Error: malloctest.c not found")
        return
    
    if not os.path.exists("bump_malloctest.c"):
        print("Error: bump_malloctest.c not found")
        return
    
    # Compile programs
    compile_programs()
    
    # Run benchmark
    benchmark_args = "1 500 1000000 10 1000"
    results = run_benchmark(benchmark_args)
    
    # Print results
    print_results(results)
    
    # Create plot
    create_plot(results)

if __name__ == "__main__":
    main()
