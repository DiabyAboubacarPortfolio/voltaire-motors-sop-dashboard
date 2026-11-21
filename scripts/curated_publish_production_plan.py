import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR, START_DATE

df_plan = pd.read_csv(
    os.path.join(STAGING_DIR, "fact_production_plan_staging.csv"),
    parse_dates=["week_start"],
)

df_plant = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Plant.csv"))
df_config = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Vehicle_Config.csv"))
valid_plants = set(df_plant["plant_id"])
valid_configs = set(df_config["config_id"])

assert df_plan.duplicated(subset=["week_start", "plant_id", "config_id"]).sum() == 0, "Duplicate week/plant/config combination"
assert df_plan["plant_id"].isin(valid_plants).all(), "A plan line references a plant_id missing from Dim_Plant"
assert df_plan["config_id"].isin(valid_configs).all(), "A plan line references a config_id missing from Dim_Vehicle_Config"
assert (df_plan["week_start"] >= pd.Timestamp(START_DATE)).all(), "A week starts before START_DATE"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Fact_Production_Plan.csv")
df_plan.to_csv(output_path, index=False)
print("Saved:", output_path)