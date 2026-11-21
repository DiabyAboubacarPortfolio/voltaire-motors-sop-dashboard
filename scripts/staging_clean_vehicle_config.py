import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_config = pd.read_csv(os.path.join(RAW_DIR, "vehicle_configs_export.csv"))

for col in ["model", "trim", "transmission"]:
    df_config[col] = df_config[col].str.strip().str.title()

df_config["list_price_usd"] = (
    df_config["list_price_usd"]
    .str.replace("$", "", regex=False)
    .str.replace(",", "", regex=False)
    .astype(int)
)

df_config = df_config.drop_duplicates()

df_config["launch_date"] = pd.to_datetime(df_config["launch_date"], format="%Y-%m-%d")
df_config["end_of_sale_date"] = pd.to_datetime(df_config["end_of_sale_date"], format="%Y-%m-%d")

output_path = os.path.join(STAGING_DIR, "dim_vehicle_config_staging.csv")
df_config.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_config.shape)
