import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_warehouse = pd.read_csv(os.path.join(RAW_DIR, "warehouses_export.csv"))
df_warehouse["warehouse_type"] = "Regional hub"

output_path = os.path.join(STAGING_DIR, "dim_warehouse_staging.csv")
df_warehouse.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_warehouse.shape)
