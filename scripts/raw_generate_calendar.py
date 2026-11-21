import pandas as pd
import holidays
import os
from config import START_DATE, END_DATE, ERP_MIGRATION_DATE, RAW_DIR

dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
years = dates.year.unique()
fr_holidays = holidays.France(years=years)
migration_date = pd.Timestamp(ERP_MIGRATION_DATE)

record_date = []
for d in dates:
    if d < migration_date:
        record_date.append(d.strftime("%m/%d/%Y"))
    else:
        record_date.append(d.strftime("%Y-%m-%d"))

source_system = []
for d in dates:
    if d < migration_date:
        source_system.append("ERP_PLANNING")
    else:
        source_system.append("ERP_PLANNING_V2")

df_calendar = pd.DataFrame({
    "record_date": record_date,
    "source_system": source_system,
})

output_path = os.path.join(RAW_DIR, "calendar_export.csv")
df_calendar.to_csv(output_path, index=False)
print("Saved:", output_path)

df_holidays = pd.DataFrame(
    sorted(fr_holidays.items()),
    columns=["holiday_date", "holiday_name"],
)

duplicate = df_holidays.iloc[[0]].copy()
duplicate["holiday_name"] = duplicate["holiday_name"].str.upper()

df_holidays = pd.concat([df_holidays, duplicate], ignore_index=True)

output_path = os.path.join(RAW_DIR, "company_holidays.csv")
df_holidays.to_csv(output_path, index=False)
print("Saved:", output_path)
