import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_customer = pd.read_csv(os.path.join(STAGING_DIR, "dim_customer_staging.csv"))

valid_regions = ["North America", "Latin America", "South West Europe",
                  "North/East/Central Europe", "APAC", "MEA","Unknown"]

assert len(df_customer) == 56061, "Row count changed"
assert df_customer["customer_id"].is_unique, "Duplicate customer_id"
assert df_customer["region"].isin(valid_regions).all(), "An unknown region is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Customer.csv")
df_customer.to_csv(output_path, index=False)
print("Saved:", output_path)
