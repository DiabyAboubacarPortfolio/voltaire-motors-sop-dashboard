"""
raw_generate_dimensions.py
--------------------------
Generates the RAW layer for the 5 Wave 1 dimensions:
    Dim_Vehicle_Config, Dim_Customer, Dim_Salesperson, Dim_Plant, Dim_Warehouse

Principle: we start from the CLEAN reference data (master_data.py), then
damage it the way a real source system would. Every injected defect is
listed in docs/data_quality_issues.md: that's the Staging check-list.
"""
import numpy as np
import pandas as pd

import master_data as md
from raw_common import add_duplicates, get_rng, mess_text, save_raw, set_nulls


# ----------------------------------------------------------------------
# 1. Dim_Vehicle_Config
# ----------------------------------------------------------------------
def raw_configs():
    rng = get_rng(21)
    df = md.build_configs()

    # Dates as ISO text; the end date stays blank if the config is still on sale
    df["launch_date"] = df["launch_date"].dt.strftime("%Y-%m-%d")
    df["end_of_sale_date"] = df["end_of_sale_date"].dt.strftime("%Y-%m-%d")

    # Defect: the price is a number for some rows, text like "$38,990" for others
    prices = df["list_price_usd"].astype(object)
    as_text = rng.random(len(df)) < 0.35
    prices[as_text] = [f"${p:,.0f}" for p in df.loc[as_text, "list_price_usd"]]
    df["list_price_usd"] = prices

    # Defect: inconsistent casing and whitespace
    for col in ["model", "trim", "transmission"]:
        df[col] = mess_text(df[col], rng, share=0.20)

    # Defect: one duplicated row
    return add_duplicates(df, rng, share=0.10)


# ----------------------------------------------------------------------
# 2. Dim_Customer (minimal version)
# ----------------------------------------------------------------------
COUNTRY_VARIANTS = {
    "USA": ["USA", "United States", "US", "U.S.A."],
    "UK": ["UK", "United Kingdom", "GB"],
    "UAE": ["UAE", "United Arab Emirates", "Emirats Arabes Unis"],
    "South Africa": ["South Africa", "RSA", "Afrique du Sud"],
    "Germany": ["Germany", "Deutschland", "Allemagne"],
    "Spain": ["Spain", "España", "Espagne"],
    "Brazil": ["Brazil", "Brasil", "Brésil"],
}


def raw_customers():
    rng = get_rng(22)
    df = md.build_customers()

    # Defect: the same country written several different ways (~10% of matching rows)
    country = df["country"].astype(object)
    for canonical, variants in COUNTRY_VARIANTS.items():
        rows = np.where((df["country"] == canonical) & (rng.random(len(df)) < 0.10))[0]
        if len(rows):
            country.iloc[rows] = rng.choice(variants[1:], size=len(rows))
    df["country"] = country

    # Defects: casing/whitespace on the region, missing segment, duplicates
    df["region"] = mess_text(df["region"], rng, share=0.03)
    df["customer_segment"] = set_nulls(df["customer_segment"], rng, share=0.01)
    return add_duplicates(df, rng, share=0.004)


# ----------------------------------------------------------------------
# 3. Dim_Salesperson
# ----------------------------------------------------------------------
def raw_salespeople():
    rng = get_rng(23)
    df = md.build_salespeople()

    # Defect: casing/whitespace on names, missing manager for a few salespeople
    df["salesperson_name"] = mess_text(df["salesperson_name"], rng, share=0.06)
    df["sales_manager_name"] = mess_text(df["sales_manager_name"], rng, share=0.06)
    df["sales_manager_id"] = set_nulls(df["sales_manager_id"], rng, share=0.03)

    # Defect: the director's name is written "First Last" or "LAST, First" depending on the row
    def flip(name):
        first, last = name.split(" ", 1)
        return f"{last.upper()}, {first}"

    directors = df["sales_director_name"].astype(object)
    flipped = rng.random(len(df)) < 0.25
    directors[flipped] = [flip(n) for n in df.loc[flipped, "sales_director_name"]]
    df["sales_director_name"] = directors
    return df


# ----------------------------------------------------------------------
# 4. Dim_Plant
# ----------------------------------------------------------------------
def raw_plants():
    df = md.build_plants()

    # Defect: three different date formats in the same column
    formats = ["%Y-%m-%d", "%d-%b-%Y", "%Y-%m-%d"]
    df["start_date"] = [d.strftime(f) for d, f in zip(df["start_date"], formats)]

    # Defect: several models in a single cell, with different separators
    df["models_produced"] = ["Aria, Orion, Atlas", "Aria;Orion", "Aria | Orion"]

    # Defect: country written differently
    df["country"] = ["United States", "Poland", "China"]
    return df


# ----------------------------------------------------------------------
# 5. Dim_Warehouse (regional hubs for finished vehicles)
# ----------------------------------------------------------------------
def raw_warehouses():
    df = md.build_warehouses()

    # Defect: the type is written with different casing and spacing
    df["warehouse_type"] = ["Regional hub", "REGIONAL HUB", "Regional Hub",
                            "regional hub", "Regional hub", "Regional hub "]
    return df


if __name__ == "__main__":
    save_raw(raw_configs(), "vehicle_configs_export.csv")
    save_raw(raw_customers(), "crm_clients_export.csv")
    save_raw(raw_salespeople(), "crm_sales_team_export.csv")
    save_raw(raw_plants(), "plants_export.csv")
    save_raw(raw_warehouses(), "warehouses_export.csv")
