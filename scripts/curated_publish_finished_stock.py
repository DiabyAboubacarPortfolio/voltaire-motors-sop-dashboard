import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_stock = pd.read_csv(
    os.path.join(STAGING_DIR, "fact_finished_vehicle_stock_staging.csv"),
    parse_dates=["snapshot_date"],
)

df_warehouse = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Warehouse.csv"))
df_config = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Vehicle_Config.csv"))
valid_warehouses = set(df_warehouse["warehouse_id"])
valid_configs = set(df_config["config_id"])

assert df_stock.duplicated(subset=["snapshot_date", "warehouse_id", "config_id"]).sum() == 0, "Duplicate snapshot/warehouse/config combination"
assert df_stock["warehouse_id"].isin(valid_warehouses).all(), "A row references a warehouse_id missing from Dim_Warehouse"
assert df_stock["config_id"].isin(valid_configs).all(), "A row references a config_id missing from Dim_Vehicle_Config"
assert (df_stock["units_in_stock"] >= 0).all(), "A negative stock value is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Fact_Finished_Vehicle_Stock.csv")
df_stock.to_csv(output_path, index=False)
print("Saved:", output_path)