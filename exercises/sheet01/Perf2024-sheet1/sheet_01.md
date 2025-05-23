Exercise Sheet 1 (Fabio Plunser)
================

A) Preparation
-------------- 

Take a look at the programs in `small_samples`. Build them, determine how to run each program, what parameters it needs and how they are set, and how the workload can be scaled.

For each program, measure the real (wall clock) time, CPU time, system time and maximum memory usage for specific executions. Empirically select a suitable set of execution parameters for each program.
Document your results, and provide an argument for why you chose a specific set of parameters.

> *Hint*  
> The program `/bin/time` can provide all the requested metrics.

Delannoy Program
-------------- 

This program calculates Delannoy numbers, which count paths in a grid. It takes a parameter N and verifies the result against pre-computed values.

```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./delannoy 14
```
The the range of the numbers is 0-23 
- 14 provides a good balance between execution time and computational complexity 


File Generator Program
-------------- 

This program creates a specified number of directories with random files of varying sizes.


Paramaters: 
- num_directories 
- num_files_per_directory 
- min_file_size 
- max_file_size 
- seed
```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./file_generator 5 200 1024 102400 1234
```
- This creates a substantial but manageable amount of data
- This creates 1000 total files should stress I/O a bit 
- The file size range (1KB-100KB) represents common file sizes
- The fixed seed ensures reproducibility of results

Find Largest File Program
-------------- 

This program recursively searches directories to find the largest file.


Run after generation files with the file_generator
```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./find_largest_file
```

Matrix Multiplication Program
-------------- 

This program multiplies matrices and verifies the result.


Default Param is 1000 seems good enough for testing
```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./matrix_mult
```

N-Body Simulation Program
-------------- 

This program simulates N particles interacting through forces.
Doesn't have paramaters: 
- N number of particels = 1000 
- M number of iterations = 100 
- L = 1000 
```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./nbody

```

Quadratic Assignment Problem (QAP) Solver
-------------- 

This program solves the QAP optimization problem.

```
/usr/bin/time -f "Real: %e s, User: %U s, System: %S s, Memory: %M KB" ./qap problems/chr12a.dat
```
Use any file from the problems folder

# Results 
> Platform: LCC Slurm 

| Program                           | User Time | System Time | Memory (kb) |
| --------------------------------- | --------- | ----------- | ----------- |
| ./delannoy 14                     | 12.29     | 0.00        | 1368        |
| ./filegen 10 200 1014 102400 1234 | 1.53      | 0.27        | 1544        |
| ./filesearch                      | 0.00      | 0.04        | 1452        |
| ./nmul                            | 0.00      | 0.00        | 888         |
| ./nbody                           | 2.55      | 0.00        | 1904        |
| ./qap problems/chr12a.dat         | 0.00      | 0.03        | 1468        |



B) Experiments
--------------

Create a simple automated experiment setup, e.g. using your favourite scripting language. All programs should be executed, each with a specified number of repetitions, and the output should include the mean of the requested performance metrics, as well as the variance. All raw data should also be stored in a structured fashion for later use.

Provide the results for each benchmark, both on one of your personal compute platforms (describe it!) as well as on the LCC3 cluster.

> With 3 Repetations for 2 different sets of parameters if program has parameters 
> 
> Platform: LCC3, single threaded

| Program       | Parameter               | Real Time (s) | User Time (s) | System Time (s) | Memory (KB) |
| ------------- | ----------------------- | ------------- | ------------- | --------------- | ----------- |
| ./delannoy 10 | 10                      | 0.020         | 0.020         | 0.00            | 1350.7      |
| ./delannoy 14 | 14                      | 12.303        | 12.280        | 0.00            | 1372        |
| ./filegen     | 5 100 1024 10240 1234   | 0.000         | 0.000         | 0.000           | 1013.3      |
| ./filegen     | 10 200 1024 102400 1234 | 0.000         | 0.000         | 0.000           | 908.0       |
| ./filesearch  | -                       | 0.000         | 0.000         | 0.000           | 949.3       |
| ./nmul        | -                       | 0.000         | 0.000         | 0.000           | 950.7       |
| ./nbody       | -                       | 2.553         | 2.553         | 0.000           | 1901.3      |
| qap           | chr10a                  | 0.247         | 0.000         | 0.030           | 1413.3      |
| qap           | chr12a                  | 0.243         | 0.003         | 0.027           | 1413.3      |

<br/>

> With 3 Repetations for 2 different sets of parameters if program has parameters 
> 
> Platform: M1 Mac 10 Core ARM64, 16GB RAM (+ swap), 1TB SSD

| Program       | Parameter               | Real Time (s) | User Time (s) | System Time (s) | Memory (KB) |
| ------------- | ----------------------- | ------------- | ------------- | --------------- | ----------- |
| ./delannoy 10 | 10                      | 0.020         | 0.020         | 0.00            | 1350.7      |
| ./delannoy 14 | 14                      | 12.303        | 12.280        | 0.00            | 1372        |
| ./filegen     | 5 100 1024 10240 1234   | 0.000         | 0.000         | 0.000           | 1013.3      |
| ./filegen     | 10 200 1024 102400 1234 | 0.000         | 0.000         | 0.000           | 908.0       |
| ./filesearch  | -                       | 0.000         | 0.000         | 0.000           | 949.3       |
| ./nmul        | -                       | 0.000         | 0.000         | 0.000           | 950.7       |
| ./nbody       | -                       | 2.553         | 2.553         | 0.000           | 1901.3      |
| qap           | chr10a                  | 0.247         | 0.000         | 0.030           | 1413.3      |
| qap           | chr12a                  | 0.243         | 0.003         | 0.027           | 1413.3      |


Submission
----------
Please submit your solutions by email to peter.thoman at UIBK, using the string "[Perf2024-sheet1]" in the subject line, before the start of the next VU at the latest.  
Try not to include attachments with a total size larger than 2 MiB.
