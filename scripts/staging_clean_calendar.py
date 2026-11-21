import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_calendar = pd.read_csv(os.path.join(RAW_DIR, "calendar_export.csv"))
is_legacy = df_calendar["source_system"] == "ERP_PLANNING"
legacy_rows = df_calendar.loc[is_legacy]
legacy_dates = pd.to_datetime(legacy_rows["record_date"], format="%m/%d/%Y")

is_v2 = df_calendar["source_system"] == "ERP_PLANNING_V2"
v2_rows = df_calendar.loc[is_v2]
v2_dates = pd.to_datetime(v2_rows["record_date"], format="%Y-%m-%d")

all_dates = pd.concat([legacy_dates, v2_dates])
df_calendar["calendar_date"] = all_dates

df_calendar["year"] = df_calendar["calendar_date"].dt.year
df_calendar["month"] = df_calendar["calendar_date"].dt.month
df_calendar["day_name"] = df_calendar["calendar_date"].dt.day_name()

df_holidays = pd.read_csv(os.path.join(RAW_DIR, "company_holidays.csv"))
df_holidays["name_key"] = df_holidays["holiday_name"].str.strip().str.lower()
df_holidays = df_holidays.drop_duplicates(subset=["holiday_date", "name_key"], keep="first")
df_holidays["holiday_date"] = pd.to_datetime(df_holidays["holiday_date"])

df_calendar = df_calendar.merge(
    df_holidays[["holiday_date", "holiday_name"]],
    left_on="calendar_date", right_on="holiday_date", how="left",
)
df_calendar["is_holiday"] = df_calendar["holiday_name"].notna()
df_calendar = df_calendar.drop(columns=["record_date", "source_system", "holiday_date"])

output_path = os.path.join(STAGING_DIR, "dim_calendar_staging.csv")
df_calendar.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_calendar.shape)
