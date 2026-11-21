import os
import re
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_plant = pd.read_csv(os.path.join(RAW_DIR, "plants_export.csv"))

df_plant["country"] = df_plant["country"].replace({"United States": "USA"})
df_plant["start_date"] = pd.to_datetime(df_plant["start_date"], format="mixed")

df_plant["models_produced"] = df_plant["models_produced"].apply(
    lambda x: [m.strip() for m in re.split(r"[,;|]", x)]
)
df_plant = df_plant.explode("models_produced").reset_index(drop=True)

output_path = os.path.join(STAGING_DIR, "dim_plant_staging.csv")
df_plant.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_plant.shape)
