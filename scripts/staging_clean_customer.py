import os
import pandas as pd
from config import RAW_DIR, STAGING_DIR

df_customer = pd.read_csv(os.path.join(RAW_DIR, "crm_clients_export.csv"))

df_customer["region"] = df_customer["region"].str.strip().str.title()
df_customer["region"] = df_customer["region"].replace({"Apac": "APAC", "Mea": "MEA"})

country_mapping = {
    "United States": "USA", "US": "USA", "U.S.A.": "USA",
    "Deutschland": "Germany", "Allemagne": "Germany",
    "United Kingdom": "UK", "GB": "UK",
    "España": "Spain", "Espagne": "Spain",
    "Brasil": "Brazil", "Brésil": "Brazil",
    "United Arab Emirates": "UAE", "Emirats Arabes Unis": "UAE",
    "Afrique du Sud": "South Africa", "RSA": "South Africa",
}
df_customer["country"] = df_customer["country"].replace(country_mapping)

df_customer = df_customer.drop_duplicates()
df_customer["customer_segment"] = df_customer["customer_segment"].fillna("Unknown")
unknown_row = pd.DataFrame([{
    "customer_id": "Unknown",
    "customer_segment": "Unknown",
    "region": "Unknown",
    "country": "Unknown",
}])
df_customer = pd.concat([df_customer, unknown_row], ignore_index=True)
output_path = os.path.join(STAGING_DIR, "dim_customer_staging.csv")
df_customer.to_csv(output_path, index=False)
print("Saved:", output_path)
print(df_customer.shape)
