import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_stock = pd.read_csv(os.path.join(RAW_DIR, "wms_finished_stock_export.csv"))

df_stock["snapshot_date"] = pd.to_datetime(df_stock["snapshot_date"], format="%d/%m/%Y")
df_stock = df_stock.drop(columns=["source_system"])
df_stock = df_stock.sort_values(["warehouse_id", "config_id", "snapshot_date"])

df_stock["has_stock_anomaly"] = df_stock["units_in_stock"] < 0
df_stock.loc[df_stock["has_stock_anomaly"], "units_in_stock"] = None
df_stock["units_in_stock"] = df_stock.groupby(["warehouse_id", "config_id"])["units_in_stock"].transform(
    lambda s: s.interpolate().round()
)

def fill_internal_gaps(group):
    warehouse_id, config_id = group.name
    full_weeks = pd.date_range(group["snapshot_date"].min(), group["snapshot_date"].max(), freq="W-SUN")
    group = group.set_index("snapshot_date").reindex(full_weeks)
    group["units_in_stock"] = group["units_in_stock"].interpolate().round()
    group["has_stock_anomaly"] = group["has_stock_anomaly"].fillna(True)
    group["warehouse_id"] = warehouse_id
    group["config_id"] = config_id
    return group

df_stock = df_stock.groupby(["warehouse_id", "config_id"], group_keys=False).apply(fill_internal_gaps, include_groups=False)
df_stock = df_stock.reset_index().rename(columns={"index": "snapshot_date"})
df_stock["units_in_stock"] = df_stock["units_in_stock"].astype(int)

output_path = os.path.join(STAGING_DIR, "fact_finished_vehicle_stock_staging.csv")
df_stock.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_stock.shape)