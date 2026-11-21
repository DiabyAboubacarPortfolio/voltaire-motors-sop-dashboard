import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_sales = pd.read_csv(os.path.join(RAW_DIR, "crm_sales_team_export.csv"))

df_sales["salesperson_name"] = df_sales["salesperson_name"].str.strip().str.title()
df_sales["sales_manager_name"] = df_sales["sales_manager_name"].str.strip().str.title()
df_sales["sales_manager_id"] = df_sales["sales_manager_id"].fillna("Unknown")

has_comma = df_sales["sales_director_name"].str.contains(",")
parts = df_sales.loc[has_comma, "sales_director_name"].str.split(", ")
fixed_names = parts.str[1] + " " + parts.str[0]
df_sales.loc[has_comma, "sales_director_name"] = fixed_names
df_sales["sales_director_name"] = df_sales["sales_director_name"].str.strip().str.title()

output_path = os.path.join(STAGING_DIR, "dim_salesperson_staging.csv")
df_sales.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_sales.shape)
