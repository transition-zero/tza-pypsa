import pandas as pd
import numpy as np

# Generate date range
date_range = pd.date_range(start='2023-01-01 00:00', end='2023-12-31 23:00', freq='H')

# Create DataFrame
df = pd.DataFrame(date_range, columns=['timestep'])

# Save to CSV
df.to_csv('./stock_models/India/snapshots.csv', index=False)