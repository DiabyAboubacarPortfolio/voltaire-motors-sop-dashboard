import os
import pandas as pd
from config import CURATED_DIR, STAGING_DIR

df_calendar = pd.read_csv(os.path.join(STAGING_DIR, "dim_calendar_staging.csv"), parse_dates=["calendar_date"])

assert len(df_calendar) == 1826, "Row count changed"
assert df_calendar["calendar_date"].notna().all(), "Missing dates"
assert df_calendar["calendar_date"].is_unique, "Duplicate dates"
assert df_calendar["calendar_date"].dtype == "datetime64[us]", "calendar_date is not a date"

print("All checks passed.")

output_path = os.path.join(CURATED_DIR, "Dim_Calendar.csv")
df_calendar.to_csv(output_path, index=False)
print("Saved:", output_path)
