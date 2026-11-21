import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_actual = pd.read_csv(os.path.join(RAW_DIR, "erp_production_actual_export.csv"))

is_legacy = df_actual["source_system"] == "ERP_PLANNING"
legacy_dates = pd.to_datetime(df_actual.loc[is_legacy, "week_start"], format="%m/%d/%Y")

is_v2 = df_actual["source_system"] == "ERP_PLANNING_V2"
v2_dates = pd.to_datetime(df_actual.loc[is_v2, "week_start"], format="%Y-%m-%d")

df_actual["week_start"] = pd.concat([legacy_dates, v2_dates])
df_actual = df_actual.drop(columns=["source_system"])
df_actual = df_actual.drop_duplicates()

output_path = os.path.join(STAGING_DIR, "fact_production_actual_staging.csv")
df_actual.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_actual.shape)