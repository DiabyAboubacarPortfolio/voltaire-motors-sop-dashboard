import os
import pandas as pd
from config import CURATED_DIR

orders = pd.read_csv(
    os.path.join(CURATED_DIR, "Fact_Customer_Orders.csv"),
    parse_dates=["order_date", "production_start_date", "delivery_date"],
)
actual = pd.read_csv(os.path.join(CURATED_DIR, "Fact_Production_Actual.csv"))
config = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Vehicle_Config.csv"))
plant = pd.read_csv(os.path.join(CURATED_DIR, "Dim_Plant.csv"))

# 1. Production must be at least as large as deliveries (some units are always in transit or in stock)
total_produced = actual["produced_units"].sum()
total_delivered = orders.loc[orders["order_status"] == "Delivered", "quantity"].sum()
assert total_produced >= total_delivered, "Delivered more units than were ever produced"

# 2. Order status must always agree with which dates are filled in
has_start = orders["production_start_date"].notna()
has_delivery = orders["delivery_date"].notna()
status = orders["order_status"]
assert ((status != "Delivered") | (has_start & has_delivery)).all(), "A Delivered order is missing a date"
assert ((status != "In Production") | (has_start & ~has_delivery)).all(), "An In Production order has the wrong dates"
assert ((status != "Confirmed") | (~has_start & ~has_delivery)).all(), "A Confirmed order already has a date"
assert ((status != "Cancelled") | (~has_start & ~has_delivery)).all(), "A Cancelled order already has a date"

# 3. A plant can only produce models it is actually equipped to build
merged = actual.merge(config[["config_id", "model"]], on="config_id").merge(
    plant[["plant_id", "models_produced"]],
    left_on=["plant_id", "model"], right_on=["plant_id", "models_produced"],
    how="left", indicator=True,
)
assert (merged["_merge"] == "both").all(), "A plant produced a model it isn't equipped for"

print("All Wave 1 integration checks passed.")
print(f"Total produced: {total_produced:,} | Total delivered: {total_delivered:,} | Gap (in transit/stock): {total_produced - total_delivered:,}")