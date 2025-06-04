# Data Structure Performance Analysis

## Analysis Components

### Access Pattern Performance
![Access Pattern Performance by Insert/Delete Ratio](scripts/plots_results_cluster/access_pattern_by_ratio_results_cluster.png)

**Description**: Compares performance across four insert/delete ratios (0%, 1%, 10%, 50%) showing operations per second on logarithmic scale.

**Key Insights**:
- Sequential access consistently outperforms random access
- Performance degrades with higher insert/delete ratios
- Different data structures(chunk sizes) show varying sensitivity to modification patterns

### Data Size Impact
![Access Pattern Impact by Data Size](scripts/plots_results_cluster/access_pattern_by_size_results_cluster.png)

**Description**: Examines how performance scales with data size (10 to 1,000,000 elements).

**Key Insights**:
- Sequential access maintains advantage across all sizes
- Some structures show better scaling characteristics

### Element Size Impact
![Element Size Impact by Ratio](scripts/plots_results_cluster/element_size_impact_by_ratio_results_cluster.png)

**Description**: Analyzes performance with different element sizes (8B, 512B, 838860B) at 0% and 50% modification ratios.

**Key Insights**:
- Larger elements favor sequential access patterns
- Memory bandwidth becomes limiting factor(see 838860B element size)

### Memory Efficiency
![Memory Efficiency by Insert/Delete Ratio](scripts/plots_results_cluster/memory_efficiency_by_ratio_results_cluster.png)

**Description**: Shows operations per MB for different modification ratios.

**Key Insights**:
- Memory efficiency varies significantly between structures
- Trade-offs between performance and memory usage(see plot above)

### Sequential vs Random Comparison
![Performance: Sequential vs Random Access Patterns](scripts/plots_results_cluster/random_vs_sequential_comparison_results_cluster.png)

**Description**: Direct bar chart comparison of access patterns.

### Relative Performance
![Relative Performance by Insert/Delete Ratio](scripts/plots_results_cluster/relative_performance_by_ratio_results_cluster.png)

**Description**: Performance normalized to array baseline across modification ratios.

**Key Insights**:
- Scenarios where alternatives outperform arrays
- Performance multipliers for different use cases

### THE LARGE PLOT

#### Element Size vs Number of Elements Ratio 0%
![element_sizexnumber_of_elements_ratio0](scripts/plots_results_cluster/ratio_0_percent_element_size_analysis_results_cluster.png)

#### Element Size vs Number of Elements Ratio 1%
![element_sizexnumber_of_elements_ratio01](scripts/plots_results_cluster/ratio_1_percent_element_size_analysis_results_cluster.png)

#### Element Size vs Number of Elements Ratio 10%
![element_sizexnumber_of_elements_ratio10](scripts/plots_results_cluster/ratio_10_percent_element_size_analysis_results_cluster.png)

#### Element Size vs Number of Elements Ratio 50%
![element_sizexnumber_of_elements_ratio50](scripts/plots_results_cluster/ratio_50_percent_element_size_analysis_results_cluster.png)

**Key Insights**:
- At 0% modification ratio, arrays more or less outperform all other structures for across all element sizes, and data sizes. After that the performance of arrays degrades significantly, while the unrolled linked list and tiered array show a more stable performance.
- At 50% modification ratio, the performance of the unrolled linked list and tiered array starts to outperform the array, especially for larger element sizes and data sizes, but even for smaller element sizes and data sizes, the performance of the unrolled linked list and tiered array is more stable than the array, which shows a significant performance degradation.
- The unrolled linked list seems to be the most stable structure across ratios, while the tiered array shows the second best stability across ratios.
- Not much is seen at the lager data size(if the run), the only thing that can be seen is that the performance of sequential access patterns is better than random access patterns, which is expected.
- At the lager element size and number of elements, the performance for all structures hit a wall, which is probably due to memory bandwidth limitations.(The array is a bit of an outlier here, showing a more pronounced degradation)

Note: Those plots are a bit packed, better view them in some kind of image viewer and switch between them to see the differences. 
## Key Findings

### 1. Sequential Access Dominance
**Observation**: Sequential access patterns consistently outperform random access across all data structures and experimental conditions.

**Magnitude**: 2-10x performance advantage in most scenarios, reaching 100x+ for large datasets.

### 2. Modification Ratio Sensitivity
**Linear Degradation**: Most structures show predictable performance decline as insert/delete ratio increases from 0% to 50%.(The normal array is a bit outlier here, showing a more pronounced degradation.)

**Structure Resilience**: Unrolled linked lists and tiered arrays demonstrate better stability under dynamic conditions compared to basic arrays.

**Critical Threshold**: Performance degradation accelerates beyond 10% modification ratio for most structures.

### 3. Tiered Array vs Unrolled Linked List
**Performance Parity**: Both structures show similar performance characteristics, with tiered arrays slightly better at a lower modification ratio, but it drops off more quickly than the unrolled linked list as the modification ratio increases.

**Memory Efficiency**: Unrolled linked lists generally show better memory efficiency across the board, especially at higher modification ratios.


---