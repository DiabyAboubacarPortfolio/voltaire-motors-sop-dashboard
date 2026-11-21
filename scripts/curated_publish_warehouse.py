import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_warehouse = pd.read_csv(os.path.join(STAGING_DIR, "dim_warehouse_staging.csv"))

assert len(df_warehouse) == 6, "Row count changed"
assert df_warehouse["warehouse_id"].is_unique, "Duplicate warehouse_id"
assert df_warehouse["warehouse_type"].isin(["Regional hub"]).all(), "An unexpected warehouse type is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Warehouse.csv")
df_warehouse.to_csv(output_path, index=False)
print("Saved:", output_path)
