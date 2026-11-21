import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_sales = pd.read_csv(os.path.join(STAGING_DIR, "dim_salesperson_staging.csv"))

valid_directors = ["Carlos Martin", "Samir Martin", "Ines Leroy",
                    "Clara Novak", "Mateo Tanaka", "Samir Ali"]

assert len(df_sales) == 90, "Row count changed"
assert df_sales["salesperson_id"].is_unique, "Duplicate salesperson_id"
assert df_sales["sales_director_name"].isin(valid_directors).all(), "An unknown director is present"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Salesperson.csv")
df_sales.to_csv(output_path, index=False)
print("Saved:", output_path)
