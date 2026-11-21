import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_config = pd.read_csv(
    os.path.join(STAGING_DIR, "dim_vehicle_config_staging.csv"),
    parse_dates=["launch_date", "end_of_sale_date"],
)

assert len(df_config) == 12, "Row count changed"
assert df_config["config_id"].is_unique, "Duplicate config_id"
assert df_config["list_price_usd"].dtype in ("int64", "float64"), "list_price_usd is not a number"
assert df_config["launch_date"].notna().all(), "Missing launch dates"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Vehicle_Config.csv")
df_config.to_csv(output_path, index=False)
print("Saved:", output_path)
