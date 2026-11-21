import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR, START_DATE

df_plan = pd.read_csv(os.path.join(RAW_DIR, "erp_production_plan_export.csv"))

is_legacy = df_plan["source_system"] == "ERP_PLANNING"
legacy_dates = pd.to_datetime(df_plan.loc[is_legacy, "week_start"], format="%m/%d/%Y")

is_v2 = df_plan["source_system"] == "ERP_PLANNING_V2"
v2_dates = pd.to_datetime(df_plan.loc[is_v2, "week_start"], format="%Y-%m-%d")

df_plan["week_start"] = pd.concat([legacy_dates, v2_dates])

df_plan = df_plan.sort_values("plan_version").drop_duplicates(
    subset=["week_start", "plant_id", "config_id"], keep="last"
)

df_plan = df_plan[df_plan["week_start"] >= pd.Timestamp(START_DATE)]
df_plan = df_plan.drop(columns=["source_system"])

output_path = os.path.join(STAGING_DIR, "fact_production_plan_staging.csv")
df_plan.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_plan.shape)