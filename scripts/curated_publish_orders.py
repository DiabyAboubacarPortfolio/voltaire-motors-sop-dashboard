import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_orders = pd.read_csv(
    os.path.join(STAGING_DIR, "fact_customer_orders_staging.csv"),
    parse_dates=["order_date", "production_start_date", "delivery_date"],
)

valid_statuses = ["Delivered", "Cancelled", "In Production", "Confirmed"]

df_config = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Vehicle_Config.csv"))
df_salesperson = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Salesperson.csv"))
valid_configs = set(df_config["config_id"])
valid_salespeople = set(df_salesperson["salesperson_id"]) | {"Unknown"}

assert len(df_orders) == 75348, "Row count changed"
assert df_orders["order_id"].is_unique, "Duplicate order_id"
assert df_orders["order_status"].isin(valid_statuses).all(), "An unknown order_status is present"
assert df_orders["config_id"].isin(valid_configs).all(), "An order references a config_id missing from Dim_Vehicle_Config"
assert df_orders["salesperson_id"].isin(valid_salespeople).all(), "An order references an unknown salesperson_id"
assert (df_orders["quantity"] > 0).all(), "A non-positive quantity is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Fact_Customer_Orders.csv")
df_orders.to_csv(output_path, index=False)
print("Saved:", output_path)