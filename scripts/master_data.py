"""
master_data.py
--------------
The "clean truth" of the Voltaire Motors world.

Key idea: we first build the CLEAN reference data in memory (configs,
customers, plants...), then each Raw script exports a deliberately
degraded version of it. Fact tables are built on top of the clean
version, so keys (customer_id, config_id...) stay consistent everywhere,
and it's the Staging cleanup that has real work to do, not the generation.

This file also holds every simulation parameter (seasonality, supply
shocks, launches...). To change the story the data tells, this is
where it happens.
"""
import numpy as np
import pandas as pd

from raw_common import get_rng

# ======================================================================
# 1. GEOGRAPHY: 6 regions, 13 countries
# ======================================================================
REGIONS = [
    "North America",
    "Latin America",
    "South West Europe",
    "North/East/Central Europe",
    "APAC",
    "MEA",
]

# Weight of each region in global demand
REGION_SHARE = {
    "North America": 0.30,
    "Latin America": 0.05,
    "South West Europe": 0.15,
    "North/East/Central Europe": 0.20,
    "APAC": 0.22,
    "MEA": 0.08,
}

# Countries in each region and their weight within the region
COUNTRIES = {
    "North America": {"USA": 0.75, "Canada": 0.15, "Mexico": 0.10},
    "Latin America": {"Brazil": 1.0},
    "South West Europe": {"France": 0.60, "Spain": 0.40},
    "North/East/Central Europe": {"Germany": 0.45, "Poland": 0.20, "UK": 0.35},
    "APAC": {"China": 0.70, "Japan": 0.30},
    "MEA": {"UAE": 0.50, "South Africa": 0.50},
}

# ======================================================================
# 2. PRODUCTS: 3 models, 12 sellable configurations
# ======================================================================
MODELS = ["Aria", "Orion", "Atlas"]

CONFIG_COLUMNS = [
    "config_id", "model", "vehicle_segment", "trim",
    "battery_capacity_kwh", "transmission", "range_km",
    "list_price_usd", "launch_date", "end_of_sale_date",
]

CONFIGS = [
    ("CFG-001", "Aria", "Compact sedan", "Essential", 52, "RWD", 410, 32900, "2020-09-01", "2024-11-30"),
    ("CFG-002", "Aria", "Compact sedan", "Comfort", 64, "RWD", 520, 37900, "2020-09-01", None),
    ("CFG-003", "Aria", "Compact sedan", "Premium", 64, "AWD", 490, 43900, "2021-06-01", None),
    ("CFG-004", "Aria", "Compact sedan", "Premium Plus", 82, "AWD", 610, 49900, "2023-02-01", None),
    ("CFG-005", "Orion", "Mid-size SUV", "Essential", 60, "RWD", 400, 41900, "2022-01-15", None),
    ("CFG-006", "Orion", "Mid-size SUV", "Comfort", 75, "RWD", 480, 46900, "2021-09-15", None),
    ("CFG-007", "Orion", "Mid-size SUV", "Premium", 75, "AWD", 455, 52900, "2021-09-15", None),
    ("CFG-008", "Orion", "Mid-size SUV", "Premium Plus", 95, "AWD", 560, 58900, "2022-05-01", None),
    ("CFG-009", "Orion", "Mid-size SUV", "Sport", 95, "AWD", 530, 66900, "2023-09-01", None),
    ("CFG-010", "Atlas", "Pickup truck", "Essential", 100, "RWD", 520, 54900, "2023-03-15", None),
    ("CFG-011", "Atlas", "Pickup truck", "Comfort", 100, "AWD", 500, 62900, "2023-03-15", None),
    ("CFG-012", "Atlas", "Pickup truck", "Premium", 130, "AWD", 640, 76900, "2024-01-15", None),
]

# Relative popularity of a config within its model (before ramp-up)
CONFIG_WEIGHT = {
    "CFG-001": 0.35, "CFG-002": 0.40, "CFG-003": 0.20, "CFG-004": 0.10,
    "CFG-005": 0.20, "CFG-006": 0.35, "CFG-007": 0.25, "CFG-008": 0.12, "CFG-009": 0.05,
    "CFG-010": 0.35, "CFG-011": 0.40, "CFG-012": 0.15,
}

# Share of each model in a region's sales (in %)
MODEL_MIX = {
    "North America": {"Aria": 25, "Orion": 50, "Atlas": 25},
    "Latin America": {"Aria": 40, "Orion": 45, "Atlas": 15},
    "South West Europe": {"Aria": 60, "Orion": 40, "Atlas": 0},
    "North/East/Central Europe": {"Aria": 55, "Orion": 45, "Atlas": 0},
    "APAC": {"Aria": 55, "Orion": 45, "Atlas": 0},
    "MEA": {"Aria": 30, "Orion": 70, "Atlas": 0},
}


def region_model_share(model):
    """For a given model, the share of its global demand that goes to each region."""
    raw = {r: REGION_SHARE[r] * MODEL_MIX[r][model] for r in REGIONS}
    total = sum(raw.values())
    return {r: v / total for r, v in raw.items()}


# ======================================================================
# 3. PLANTS AND WAREHOUSES
# ======================================================================
# Which plant serves which region, and which hub receives its vehicles
REGION_FACTORY = {
    "North America": "USN-01",
    "Latin America": "USN-01",
    "South West Europe": "USN-02",
    "North/East/Central Europe": "USN-02",
    "MEA": "USN-02",
    "APAC": "USN-03",
}
REGION_HUB = {
    "North America": "HUB-01",
    "Latin America": "HUB-02",
    "South West Europe": "HUB-03",
    "North/East/Central Europe": "HUB-04",
    "APAC": "HUB-05",
    "MEA": "HUB-06",
}
# Models manufactured by each plant
FACTORY_MODELS = {
    "USN-01": ["Aria", "Orion", "Atlas"],
    "USN-02": ["Aria", "Orion"],
    "USN-03": ["Aria", "Orion"],
}
# Transit time plant -> regional hub (min, max days)
TRANSIT_DAYS = {
    ("USN-01", "North America"): (4, 9),
    ("USN-01", "Latin America"): (18, 30),
    ("USN-02", "South West Europe"): (4, 8),
    ("USN-02", "North/East/Central Europe"): (3, 7),
    ("USN-02", "MEA"): (22, 35),
    ("USN-03", "APAC"): (5, 12),
}

# ======================================================================
# 4. DEMAND: customer segments, growth curves, seasonality
# ======================================================================
SEGMENTS = ["B2C", "B2B fleet", "B2G", "Leasing"]
SEG_UNIT_SHARE = {"B2C": 0.82, "B2B fleet": 0.10, "B2G": 0.03, "Leasing": 0.05}
SEG_MEAN_QTY = {"B2C": 1.05, "B2B fleet": 8.0, "B2G": 13.0, "Leasing": 27.0}
SEG_DISCOUNT = {"B2C": (0.00, 0.03), "B2B fleet": (0.05, 0.12), "B2G": (0.08, 0.15), "Leasing": (0.06, 0.10)}
SEG_ADMIN_DELAY = {"B2C": (2, 7), "B2B fleet": (5, 14), "B2G": (10, 30), "Leasing": (7, 20)}
SEG_DWELL_DAYS = {"B2C": (3, 14), "B2B fleet": (5, 21), "B2G": (5, 21), "Leasing": (5, 21)}
SEG_CANCEL_FACTOR = {"B2C": 1.1, "B2B fleet": 0.8, "B2G": 0.4, "Leasing": 0.6}
N_CUSTOMERS = {"B2C": 55000, "B2B fleet": 900, "B2G": 120, "Leasing": 40}

# Global weekly demand by model (units/week), interpolated between these points.
# Before the first point, demand is 0 (the model doesn't exist yet).
MODEL_ANCHORS = {
    "Aria": [("2020-12-01", 90), ("2021-12-31", 140), ("2022-12-31", 155),
             ("2023-12-31", 175), ("2024-12-31", 185), ("2025-12-31", 170)],
    "Orion": [("2021-09-15", 0), ("2021-12-31", 60), ("2022-12-31", 110),
              ("2023-12-31", 200), ("2024-12-31", 270), ("2025-12-31", 310)],
    "Atlas": [("2023-03-15", 0), ("2023-12-31", 80), ("2024-12-31", 110),
              ("2025-12-31", 145)],
}

# Monthly multiplier (January -> December): quarter-end and year-end peaks
SEASONALITY = [0.85, 0.85, 1.12, 0.92, 0.92, 1.08, 0.90, 0.86, 1.10, 0.97, 1.05, 1.28]

# Demand shocks: (label, start, end, multiplier)
DEMAND_EVENTS = [
    ("End of COVID cycle, hesitant demand", "2021-01-01", "2021-03-31", 0.90),
    ("Fuel price spike", "2022-06-01", "2022-12-31", 1.08),
    ("Rising credit rates", "2023-07-01", "2023-12-31", 0.93),
]

# Evolution of the average price actually charged relative to list price
PRICE_YEAR_FACTOR = {2021: 1.00, 2022: 1.05, 2023: 1.02, 2024: 0.98, 2025: 0.98}

# Base cancellation probability, by order year
CANCEL_BASE = {2021: 0.12, 2022: 0.09, 2023: 0.055, 2024: 0.05, 2025: 0.05}

# ======================================================================
# 5. SUPPLY: events that reduce production capacity
# ======================================================================
# (label, plant or None=all, start, end, availability multiplier)
SUPPLY_EVENTS = [
    ("Global semiconductor shortage Q1 2021", None, "2021-01-01", "2021-03-31", 0.75),
    ("Global semiconductor shortage Q2 2021", None, "2021-04-01", "2021-06-30", 0.62),
    ("Global semiconductor shortage Q3 2021", None, "2021-07-01", "2021-09-30", 0.55),
    ("Global semiconductor shortage Q4 2021", None, "2021-10-01", "2021-12-31", 0.65),
    ("Global semiconductor shortage Q1 2022", None, "2022-01-01", "2022-03-31", 0.78),
    ("Global semiconductor shortage Q2 2022", None, "2022-04-01", "2022-06-30", 0.85),
    ("Global semiconductor shortage Q3 2022", None, "2022-07-01", "2022-09-30", 0.93),
    ("Guangzhou lockdown", "USN-03", "2022-04-04", "2022-06-05", 0.35),
    ("Fire at a battery cell supplier", "USN-02", "2023-05-08", "2023-06-18", 0.60),
    ("Strike and severe weather in Ohio", "USN-01", "2024-02-05", "2024-03-03", 0.50),
    ("ERP migration disruptions", None, "2025-07-01", "2025-08-15", 0.75),
]

# Nominal capacity = HEADROOM x smoothed average demand
CAPACITY_HEADROOM = 1.12

# Production plan bias (the plan is more optimistic than reality)
PLAN_BIAS = {2021: 1.10, 2022: 1.08, 2023: 1.04, 2024: 1.03, 2025: 1.03}

# ======================================================================
# 6. BUILDING THE CLEAN DIMENSIONS
# ======================================================================
FIRST_NAMES = [
    "Lucas", "Emma", "Noah", "Chloé", "Liam", "Sofia", "Hugo", "Amira", "Mateo", "Ines",
    "Oliver", "Yuki", "Ahmed", "Clara", "Daniel", "Fatima", "Marco", "Priya", "Jonas", "Leila",
    "Thomas", "Aiko", "Carlos", "Nadia", "Victor", "Elena", "Samir", "Julia", "Ivan", "Mei",
]
LAST_NAMES = [
    "Martin", "Silva", "Novak", "Tanaka", "Haddad", "Schmidt", "Rossi", "Kowalski", "Okafor", "Chen",
    "Dubois", "Garcia", "Nielsen", "Petrov", "Sato", "Moreau", "Ali", "Fischer", "Costa", "Wang",
    "Lopez", "Bernard", "Khan", "Ivanov", "Hughes", "Rahman", "Weber", "Mendes", "Park", "Leroy",
]
MANAGERS_PER_REGION = {
    "North America": 4, "Latin America": 2, "South West Europe": 3,
    "North/East/Central Europe": 4, "APAC": 3, "MEA": 2,
}


def build_configs():
    df = pd.DataFrame(CONFIGS, columns=CONFIG_COLUMNS)
    df["launch_date"] = pd.to_datetime(df["launch_date"])
    df["end_of_sale_date"] = pd.to_datetime(df["end_of_sale_date"])
    return df


def build_plants():
    rows = [
        ("USN-01", "Giga Ohio", "USA", "North America", "2019-06-01", "Aria, Orion, Atlas"),
        ("USN-02", "Giga Silesia", "Poland", "North/East/Central Europe", "2020-03-01", "Aria, Orion"),
        ("USN-03", "Giga Guangzhou", "China", "APAC", "2020-11-01", "Aria, Orion"),
    ]
    cols = ["plant_id", "plant_name", "country", "region", "start_date", "models_produced"]
    df = pd.DataFrame(rows, columns=cols)
    df["start_date"] = pd.to_datetime(df["start_date"])
    return df


def build_warehouses():
    rows = [
        ("HUB-01", "Hub Columbus", "Regional hub", "USA", "North America", "USN-01"),
        ("HUB-02", "Hub São Paulo", "Regional hub", "Brazil", "Latin America", "USN-01"),
        ("HUB-03", "Hub Barcelona", "Regional hub", "Spain", "South West Europe", "USN-02"),
        ("HUB-04", "Hub Hamburg", "Regional hub", "Germany", "North/East/Central Europe", "USN-02"),
        ("HUB-05", "Hub Shanghai", "Regional hub", "China", "APAC", "USN-03"),
        ("HUB-06", "Hub Dubai", "Regional hub", "UAE", "MEA", "USN-02"),
    ]
    cols = ["warehouse_id", "warehouse_name", "warehouse_type", "country", "region", "supplying_plant_id"]
    return pd.DataFrame(rows, columns=cols)


def build_salespeople():
    """Hierarchy: Sales Director (per region) > Sales Manager > Salesperson."""
    rng = get_rng(11)
    rows = []
    mgr_counter, rep_counter = 1, 1
    for region in REGIONS:
        director = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        for _ in range(MANAGERS_PER_REGION[region]):
            mgr_id = f"MGR-{mgr_counter:02d}"
            mgr_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            mgr_counter += 1
            for _ in range(int(rng.integers(4, 7))):
                rep_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
                rows.append((f"COM-{rep_counter:03d}", rep_name, mgr_id, mgr_name, region, director))
                rep_counter += 1
    cols = ["salesperson_id", "salesperson_name", "sales_manager_id",
            "sales_manager_name", "region", "sales_director_name"]
    return pd.DataFrame(rows, columns=cols)


def build_customers():
    """Minimal version of Dim_Customer (enriched in Wave 3)."""
    rng = get_rng(12)
    frames = []
    for seg, total in N_CUSTOMERS.items():
        for region in REGIONS:
            k = max(2, int(round(total * REGION_SHARE[region])))
            countries = list(COUNTRIES[region])
            probs = list(COUNTRIES[region].values())
            frames.append(pd.DataFrame({
                "customer_segment": seg,
                "region": region,
                "country": rng.choice(countries, size=k, p=probs),
            }))
    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1, random_state=7).reset_index(drop=True)
    numbers = pd.Series(np.arange(1, len(df) + 1)).astype(str).str.zfill(6)
    df.insert(0, "customer_id", "CUST-" + numbers)
    return df
