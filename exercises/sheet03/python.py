import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file into a pandas DataFrame
df = pd.read_csv('profile.csv')

# Set 'Metric' column as index
df = df.set_index('Metric')

# Plotting
ax = df.plot(kind='bar', figsize=(12, 8), rot=45)
plt.title('Runtime Breakdown by Function and Configuration')
plt.xlabel('Function')
plt.ylabel('Runtime (seconds)')
plt.tight_layout()

# Add value labels on top of the bars
for p in ax.patches:
    ax.annotate(
        str(round(p.get_height(), 2)),
        (p.get_x() + p.get_width() / 2., p.get_height()),
        ha='center',
        va='center',
        xytext=(0, 10),
        textcoords='offset points',
        fontsize=8,
    )

plt.savefig('performance_profile.png')  # Save the figure
plt.show()
