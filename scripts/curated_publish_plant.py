import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_plant = pd.read_csv(
    os.path.join(STAGING_DIR, "dim_plant_staging.csv"),
    parse_dates=["start_date"],
)

valid_countries = ["USA", "Poland", "China"]

assert len(df_plant) == 7, "Row count changed"
assert df_plant.duplicated(subset=["plant_id", "models_produced"]).sum() == 0, "Duplicate plant/model combination"
assert df_plant["country"].isin(valid_countries).all(), "An unknown country is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Plant.csv")
df_plant.to_csv(output_path, index=False)
print("Saved:", output_path)
