import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_orders = pd.read_csv(os.path.join(RAW_DIR, "crm_orders_export.csv"))
df_orders = df_orders.drop_duplicates()

df_orders["order_date"] = pd.to_datetime(df_orders["order_date"], format="%Y-%m-%d %H:%M:%S")
df_orders["production_start_date"] = pd.to_datetime(df_orders["production_start_date"], format="%Y-%m-%d")
df_orders["delivery_date"] = pd.to_datetime(df_orders["delivery_date"], format="%Y-%m-%d")

df_orders["order_status"] = df_orders["order_status"].str.strip().str.title()
df_orders["config_id"] = df_orders["config_id"].str.strip().str.upper()
df_orders["salesperson_id"] = df_orders["salesperson_id"].fillna("Unknown")

df_customer = pd.read_csv(os.path.join(STAGING_DIR, "dim_customer_staging.csv"))
known_customers = set(df_customer["customer_id"])
is_orphan = ~df_orders["customer_id"].isin(known_customers)
df_orders.loc[is_orphan, "customer_id"] = "Unknown"

is_impossible = df_orders["production_start_date"] < df_orders["order_date"].dt.normalize()
df_orders["has_date_anomaly"] = is_impossible

output_path = os.path.join(STAGING_DIR, "fact_customer_orders_staging.csv")
df_orders.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_orders.shape)