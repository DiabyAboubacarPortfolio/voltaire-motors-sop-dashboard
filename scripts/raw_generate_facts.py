"""
raw_generate_facts.py
----------------------
Generates the RAW layer for the 4 Wave 1 fact tables:
    Fact_Customer_Orders, Fact_Production_Plan,
    Fact_Production_Actual, Fact_Finished_Vehicle_Stock

Why ONE script for 4 tables? Because they tell the same story:
    customer order -> plant queue -> production -> transport -> hub -> delivery
If each table were generated separately, the numbers wouldn't reconcile
(we'd produce more than we sell, stock would go negative...).
So we simulate ONE order chain, and derive the 4 tables from it.

Steps:
    1. Demand      : how many orders per week, region, model, segment
    2. Orders      : one row per order (customer, config, salesperson, price...)
    3. Production  : FIFO queue per plant, limited by capacity
    4. Delivery    : transport to the hub, then hand-off to the customer
    5. Tables      : plan, actual production, stock, orders -> "messy" version
"""
import numpy as np
import pandas as pd

import master_data as md
from config import END_DATE, ERP_MIGRATION_DATE, START_DATE
from raw_common import add_duplicates, get_rng, mess_text, save_raw, set_nulls

START = pd.Timestamp(START_DATE)
END = pd.Timestamp(END_DATE)
MIGRATION = pd.Timestamp(ERP_MIGRATION_DATE)

# Weekly grid: Mondays, from the week of day 1 through to the end
WEEK_STARTS = pd.date_range(START - pd.Timedelta(days=START.weekday()), END, freq="W-MON")
T = len(WEEK_STARTS)
MONDAYS = WEEK_STARTS.values.astype("datetime64[D]")
WEEK0 = MONDAYS[0]
WEEK_MID = MONDAYS + np.timedelta64(3, "D")
D_START = np.datetime64(START.date(), "D")
D_END = np.datetime64(END.date(), "D")
D_MIGRATION = np.datetime64(MIGRATION.date(), "D")
NAT = np.datetime64("NaT", "D")
WEEKDAY_P = np.array([0.18, 0.19, 0.19, 0.18, 0.16, 0.06, 0.04])   # Monday -> Sunday


def week_index(dates):
    """Week number (0, 1, 2...) of each date."""
    return ((dates - WEEK0) // np.timedelta64(7, "D")).astype(int)


def days(values):
    return np.asarray(values).astype("timedelta64[D]")


def uniform_int(rng, low, high, size):
    """Random integer between low and high inclusive; low/high can be arrays."""
    low, high = np.asarray(low), np.asarray(high)
    return low + (rng.random(size) * (high - low + 1)).astype(int)


# ======================================================================
# STEP 1: a model's weekly demand
# ======================================================================
def model_weekly_units(model, rng):
    """Units demanded each week (worldwide) for a model."""
    anchors = md.MODEL_ANCHORS[model]
    anchor_days = np.array([np.datetime64(d, "D").astype(int) for d, _ in anchors])
    anchor_vals = np.array([v for _, v in anchors], dtype=float)
    rate = np.interp(WEEK_MID.astype(int), anchor_days, anchor_vals, left=0.0)

    months = pd.DatetimeIndex(WEEK_MID).month.values
    seasonality = np.array(md.SEASONALITY)[months - 1]

    events = np.ones(T)
    for _, start, end, mult in md.DEMAND_EVENTS:
        mask = (WEEK_MID >= np.datetime64(start)) & (WEEK_MID <= np.datetime64(end))
        events[mask] *= mult

    noise = rng.lognormal(0, 0.08, T)
    return rate * seasonality * events * noise


# ======================================================================
# STEP 2: the orders
# ======================================================================
def draw_quantities(segment, n, rng):
    if segment == "B2C":
        return np.where(rng.random(n) < 0.95, 1, 2)
    params = {"B2B fleet": (1.9, 0.6, 3, 60), "B2G": (2.4, 0.6, 5, 80), "Leasing": (3.2, 0.5, 10, 150)}
    mu, sigma, low, high = params[segment]
    return np.clip(rng.lognormal(mu, sigma, n).round(), low, high).astype(int)


def build_orders(rng, cfg, customers, salespeople):
    cfg_by_model = {m: cfg[cfg["model"] == m].reset_index(drop=True) for m in md.MODELS}
    customers_by = {k: g.reset_index(drop=True) for k, g in customers.groupby(["region", "customer_segment"])}
    parts = []

    for model in md.MODELS:
        weekly_units = model_weekly_units(model, rng)
        share_by_region = md.region_model_share(model)
        cfgs = cfg_by_model[model]
        launch = cfgs["launch_date"].values.astype("datetime64[D]")
        end = cfgs["end_of_sale_date"].fillna(pd.Timestamp("2100-01-01")).values.astype("datetime64[D]")
        base_w = np.array([md.CONFIG_WEIGHT[i] for i in cfgs["config_id"]])
        model_first_launch = launch.min()

        for region in md.REGIONS:
            region_share = share_by_region[region]
            if region_share == 0:
                continue
            rep_ids = salespeople.loc[salespeople["region"] == region, "salesperson_id"].values
            countries = list(md.COUNTRIES[region])

            for seg in md.SEGMENTS:
                # Number of orders per week = units / average order size
                lam = weekly_units * region_share * md.SEG_UNIT_SHARE[seg] / md.SEG_MEAN_QTY[seg]
                counts = rng.poisson(lam)
                n = int(counts.sum())
                if n == 0:
                    continue

                # Order date: week drawn, then day of the week
                wk = np.repeat(np.arange(T), counts)
                dates = MONDAYS[wk] + rng.choice(7, size=n, p=WEEKDAY_P).astype("timedelta64[D]")
                dates = np.maximum(dates, model_first_launch)
                keep = (dates >= D_START) & (dates <= D_END)
                dates, n = dates[keep], int(keep.sum())

                # Config choice among those actually on sale that day
                age = (dates[:, None] - launch[None, :]).astype(int)
                available = (age >= 0) & (dates[:, None] < end[None, :])
                ramp = 0.05 + 0.95 * (1 - np.exp(-np.clip(age, 0, None) / 90))
                weights = base_w[None, :] * available * ramp
                probs = weights / weights.sum(axis=1, keepdims=True)
                pick = (probs.cumsum(axis=1) < rng.random(n)[:, None]).sum(axis=1)
                pick = np.minimum(pick, len(cfgs) - 1)

                # Customer (within the region and segment) and delivery country
                pool = customers_by[(region, seg)]
                chosen = rng.integers(0, len(pool), n)
                country = pool["country"].values[chosen]
                other = rng.choice(countries, n)
                country = np.where(rng.random(n) < 0.03, other, country)

                parts.append(pd.DataFrame({
                    "order_day": dates,
                    "region": region,
                    "customer_segment": seg,
                    "model": model,
                    "customer_id": pool["customer_id"].values[chosen],
                    "config_id": cfgs["config_id"].values[pick],
                    "salesperson_id": rng.choice(rep_ids, n),
                    "delivery_country": country,
                    "quantity": draw_quantities(seg, n, rng),
                }))

    orders = pd.concat(parts, ignore_index=True)

    # Order time, then sort chronologically and number the orders
    seconds = rng.integers(7 * 3600, 22 * 3600, len(orders))
    orders["order_date"] = pd.to_datetime(orders["order_day"]) + pd.to_timedelta(seconds, unit="s")
    orders = orders.sort_values("order_date", kind="stable").reset_index(drop=True)
    numbers = pd.Series(np.arange(1, len(orders) + 1)).astype(str).str.zfill(6)
    orders["order_id"] = "ORD-" + numbers

    # Price: list price x yearly evolution x segment discount
    list_price = orders["config_id"].map(cfg.set_index("config_id")["list_price_usd"])
    year = orders["order_date"].dt.year
    low = orders["customer_segment"].map({s: v[0] for s, v in md.SEG_DISCOUNT.items()}).values
    high = orders["customer_segment"].map({s: v[1] for s, v in md.SEG_DISCOUNT.items()}).values
    discount = low + rng.random(len(orders)) * (high - low)
    orders["unit_price_usd"] = (list_price * year.map(md.PRICE_YEAR_FACTOR) * (1 - discount)).round(0)

    # Cancellation: more frequent in 2021-2022 (long waits) and after the ERP migration
    p_cancel = year.map(md.CANCEL_BASE) * orders["customer_segment"].map(md.SEG_CANCEL_FACTOR)
    p_cancel = p_cancel + np.where(orders["order_day"].values >= D_MIGRATION, 0.02, 0.0)
    orders["cancelled"] = rng.random(len(orders)) < p_cancel.values

    orders["plant_id"] = orders["region"].map(md.REGION_FACTORY)
    return orders


# ======================================================================
# STEP 3: production (FIFO queue per plant)
# ======================================================================
def availability(factory_id):
    """Share of capacity actually available each week (supply shocks)."""
    avail = np.ones(T)
    for _, factory, start, end, mult in md.SUPPLY_EVENTS:
        if factory in (None, factory_id):
            mask = (WEEK_MID >= np.datetime64(start)) & (WEEK_MID <= np.datetime64(end))
            avail[mask] *= mult
    return avail


def run_queue(arrivals, capacity, first_pos, last_pos):
    """Simulates a plant: each week it produces at most 'capacity' units,
    in order of order arrival (FIFO).

    Returns, for each order, the week its 1st unit starts
    and the week its last unit starts.
    """
    cumulative = np.zeros(T)
    backlog, done = 0.0, 0.0
    for t in range(T):
        stock_to_serve = backlog + arrivals[t]
        served = min(capacity[t], stock_to_serve)
        backlog = stock_to_serve - served
        done += served
        cumulative[t] = done
    start_week = np.searchsorted(cumulative, first_pos, side="left")
    end_week = np.searchsorted(cumulative, last_pos, side="left")
    return start_week, end_week


def simulate_production(orders, rng):
    n = len(orders)
    qty = orders["quantity"].values
    seg = orders["customer_segment"]

    # Administrative delay before the order is eligible for production
    lo = seg.map({s: v[0] for s, v in md.SEG_ADMIN_DELAY.items()}).values
    hi = seg.map({s: v[1] for s, v in md.SEG_ADMIN_DELAY.items()}).values
    eligible = orders["order_day"].values.astype("datetime64[D]") + days(uniform_int(rng, lo, hi, n))
    elig_week = week_index(eligible)

    d_start = np.full(n, NAT)
    d_end = np.full(n, NAT)
    capacity_nominal = {}

    for factory in md.FACTORY_MODELS:
        idx = np.where((orders["plant_id"].values == factory) & (~orders["cancelled"].values) & (elig_week < T))[0]
        idx = idx[np.argsort(eligible[idx], kind="stable")]           # arrival order
        arrivals = np.bincount(elig_week[idx], weights=qty[idx], minlength=T)

        # Nominal capacity: follows demand smoothed over 52 weeks, with headroom
        smooth = pd.Series(arrivals).rolling(52, center=True, min_periods=26).mean().values
        capacity_nominal[factory] = md.CAPACITY_HEADROOM * smooth
        capacity = capacity_nominal[factory] * availability(factory)

        last_pos = np.cumsum(qty[idx])
        first_pos = last_pos - qty[idx] + 1
        start_w, end_w = run_queue(arrivals, capacity, first_pos, last_pos)

        m = len(idx)
        start_day = MONDAYS[np.minimum(start_w, T - 1)] + days(rng.integers(0, 5, m))
        start_day = np.maximum(start_day, eligible[idx])
        build = rng.integers(3, 9, m) + np.minimum(qty[idx] // 10, 10)
        end_day = MONDAYS[np.minimum(end_w, T - 1)] + days(rng.integers(0, 5, m))
        end_day = np.maximum(end_day, start_day) + days(build)

        start_day = np.where((start_w < T) & (start_day <= D_END), start_day, NAT)
        end_day = np.where((end_w < T) & (end_day <= D_END), end_day, NAT)
        d_start[idx], d_end[idx] = start_day, end_day

    orders["production_start_date"] = d_start
    orders["production_end_date"] = d_end
    return orders, capacity_nominal


# ======================================================================
# STEP 4: transport to the hub, then delivery to the customer
# ======================================================================
def simulate_delivery(orders, rng):
    n = len(orders)
    factory = orders["plant_id"].values
    region = orders["region"].values
    d_end = orders["production_end_date"].values.astype("datetime64[D]")

    lo = np.array([md.TRANSIT_DAYS[(f, r)][0] for f, r in zip(factory, region)])
    hi = np.array([md.TRANSIT_DAYS[(f, r)][1] for f, r in zip(factory, region)])
    arrival = d_end + days(uniform_int(rng, lo, hi, n))

    seg = orders["customer_segment"]
    dlo = seg.map({s: v[0] for s, v in md.SEG_DWELL_DAYS.items()}).values
    dhi = seg.map({s: v[1] for s, v in md.SEG_DWELL_DAYS.items()}).values
    delivery = arrival + days(uniform_int(rng, dlo, dhi, n))

    orders["hub_arrival_date"] = np.where(arrival <= D_END, arrival, NAT)
    orders["delivery_date"] = np.where(delivery <= D_END, delivery, NAT)

    # Status as of the end of the simulation
    status = np.where(orders["delivery_date"].notna(), "Delivered",
             np.where(orders["production_start_date"].notna(), "In production", "Confirmed"))
    orders["order_status"] = np.where(orders["cancelled"], "Cancelled", status)
    return orders


# ======================================================================
# STEP 5a: Fact_Customer_Orders (messy version)
# ======================================================================
STATUS_VARIANTS = {
    "Delivered": ["DELIVERED", "delivered", " Delivered"],
    "In production": ["in production", "In Production", "IN PRODUCTION"],
    "Confirmed": ["CONFIRMED", "confirmed", " Confirmed"],
    "Cancelled": ["CANCELLED", "cancelled", " Cancelled"],
}


def raw_orders(orders, rng):
    df = pd.DataFrame({
        "order_id": orders["order_id"],
        "order_date": orders["order_date"],
        "customer_id": orders["customer_id"],
        "config_id": orders["config_id"],
        "salesperson_id": orders["salesperson_id"],
        "delivery_country": orders["delivery_country"],
        "quantity": orders["quantity"],
        "unit_price_usd": orders["unit_price_usd"],
        "order_status": orders["order_status"],
        "production_start_date": pd.to_datetime(orders["production_start_date"]),
        "delivery_date": pd.to_datetime(orders["delivery_date"]),
    })

    # Defect: a few production start dates earlier than the order date (data entry error)
    started = np.where(df["production_start_date"].notna())[0]
    bad = rng.choice(started, size=int(len(started) * 0.002), replace=False)
    order_day = df["order_date"].dt.normalize().iloc[bad]
    df.loc[df.index[bad], "production_start_date"] = order_day - pd.to_timedelta(rng.integers(1, 11, len(bad)), unit="D")

    # Turn dates into text (the CRM exports everything as text)
    df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["production_start_date"] = df["production_start_date"].dt.strftime("%Y-%m-%d")
    df["delivery_date"] = df["delivery_date"].dt.strftime("%Y-%m-%d")

    # Defect: inconsistent status labels (casing) on ~10% of rows
    status = df["order_status"].astype(object)
    for pos in np.where(rng.random(len(df)) < 0.10)[0]:
        status.iloc[pos] = rng.choice(STATUS_VARIANTS[status.iloc[pos]])
    df["order_status"] = status

    # Defects: damaged config_id, missing salespeople, unknown customers (orphans)
    df["config_id"] = mess_text(df["config_id"], rng, share=0.012)
    df["salesperson_id"] = set_nulls(df["salesperson_id"], rng, share=0.01)
    customers = df["customer_id"].astype(object)
    orphans = rng.choice(len(df), size=int(len(df) * 0.0025), replace=False)
    customers.iloc[orphans] = [f"CUST-{x}" for x in rng.integers(900000, 999999, len(orphans))]
    df["customer_id"] = customers

    # Defect: exact duplicates (double click on "submit")
    return add_duplicates(df, rng, share=0.005)


# ======================================================================
# STEP 5b: Fact_Production_Plan and Fact_Production_Actual
# ======================================================================
def format_erp_dates(week_dates):
    """Before the migration: US format and ERP_PLANNING system; after: ISO and ERP_PLANNING_V2."""
    dates = pd.Series(pd.to_datetime(week_dates))
    legacy = (dates < MIGRATION).values
    text = np.where(legacy, dates.dt.strftime("%m/%d/%Y"), dates.dt.strftime("%Y-%m-%d"))
    system = np.where(legacy, "ERP_PLANNING", "ERP_PLANNING_V2")
    return text, system


def duplicate_go_live_rows(df, week_col_dates):
    """Defect: the first 3 weeks after the migration were loaded twice."""
    dates = pd.to_datetime(week_col_dates)
    mask = (dates >= MIGRATION) & (dates < MIGRATION + pd.Timedelta(days=21))
    return pd.concat([df, df[np.asarray(mask)]]).sort_index(kind="stable").reset_index(drop=True)


def raw_plan(orders, capacity_nominal, cfg, rng):
    factories = list(md.FACTORY_MODELS)
    configs = list(cfg["config_id"])
    f_pos = {f: i for i, f in enumerate(factories)}
    c_pos = {c: i for i, c in enumerate(configs)}

    # Raw demand (cancellations included) by plant x config x week:
    # this is what planners "see" when they build the plan
    demand = np.zeros((len(factories), len(configs), T))
    w = week_index(orders["order_day"].values.astype("datetime64[D]"))
    ok = w < T
    np.add.at(demand, (orders["plant_id"].map(f_pos).values[ok], orders["config_id"].map(c_pos).values[ok], w[ok]),
              orders["quantity"].values[ok])

    years = np.clip(pd.DatetimeIndex(WEEK_MID).year.values, 2021, 2025)   # first and last week spill into 2020 and 2026
    bias = np.array([md.PLAN_BIAS[y] for y in years])
    post_go_live = (WEEK_MID >= D_MIGRATION) & (WEEK_MID < D_MIGRATION + np.timedelta64(120, "D"))
    bias = np.where(post_go_live, bias * 1.08, bias)
    sigma = np.where(post_go_live, 0.20, 0.10)

    plan = np.zeros_like(demand)
    valid = np.zeros_like(demand, dtype=bool)
    for f in factories:
        for _, c in cfg.iterrows():
            if c["model"] not in md.FACTORY_MODELS[f]:
                continue
            fi, ci = f_pos[f], c_pos[c["config_id"]]
            smooth = np.convolve(demand[fi, ci], np.ones(5) / 5, mode="same")
            launch_w = int(week_index(np.array([c["launch_date"]], dtype="datetime64[D]"))[0])
            since = np.arange(T) - launch_w
            boost = np.where(since >= 0, 1 + 0.35 * np.exp(-since / 20.0), 1.0)   # overly optimistic ramp-up
            plan[fi, ci] = smooth * bias * boost * np.exp(rng.normal(0, sigma))
            last_w = T - 1
            if pd.notna(c["end_of_sale_date"]):
                last_w = int(week_index(np.array([c["end_of_sale_date"]], dtype="datetime64[D]"))[0]) + 4
            valid[fi, ci, max(launch_w - 2, 0):min(last_w, T - 1) + 1] = True

    # The plan cannot exceed the plant's nominal capacity
    for f in factories:
        fi = f_pos[f]
        total = plan[fi].sum(axis=0)
        scale = np.minimum(1.0, capacity_nominal[f] / np.maximum(total, 1e-9))
        plan[fi] *= np.nan_to_num(scale, nan=1.0)

    f_idx, c_idx, t_idx = np.nonzero(valid)
    df = pd.DataFrame({
        "week_monday": MONDAYS[t_idx],
        "plant_id": np.array(factories)[f_idx],
        "config_id": np.array(configs)[c_idx],
        "planned_units": np.rint(plan[f_idx, c_idx, t_idx]).astype(int),
        "plan_version": 1,
    })

    # Defect: ~3% of rows were revised (version 2); the old version stays in the export
    revised = rng.random(len(df)) < 0.03
    old = df[revised].copy()
    old["planned_units"] = np.rint(old["planned_units"] * rng.uniform(0.7, 1.3, len(old))).astype(int)
    df.loc[revised, "plan_version"] = 2
    df = pd.concat([old, df]).sort_values(["week_monday", "plant_id", "config_id", "plan_version"], kind="stable")
    df = df.reset_index(drop=True)

    text, system = format_erp_dates(df["week_monday"].values)
    out = pd.DataFrame({
        "source_system": system,
        "week_start": text,
        "plant_id": df["plant_id"],
        "config_id": df["config_id"],
        "planned_units": df["planned_units"],
        "plan_version": df["plan_version"],
    })
    return duplicate_go_live_rows(out, df["week_monday"].values)


def raw_production(orders):
    done = orders[orders["production_end_date"].notna()].copy()
    done["week"] = week_index(done["production_end_date"].values.astype("datetime64[D]"))
    done = done[done["week"] < T]
    grouped = done.groupby(["week", "plant_id", "config_id"], as_index=False)["quantity"].sum()
    grouped = grouped.sort_values(["week", "plant_id", "config_id"]).reset_index(drop=True)

    text, system = format_erp_dates(MONDAYS[grouped["week"].values])
    out = pd.DataFrame({
        "source_system": system,
        "week_start": text,
        "plant_id": grouped["plant_id"],
        "config_id": grouped["config_id"],
        "produced_units": grouped["quantity"],
    })
    return duplicate_go_live_rows(out, MONDAYS[grouped["week"].values])


# ======================================================================
# STEP 5c: Fact_Finished_Vehicle_Stock
# ======================================================================
def raw_stock(orders, cfg, rng):
    """Weekly stock (Sunday) by hub and by config:
    vehicles that arrived at the hub and haven't been handed off yet."""
    snapshots = pd.date_range(START, END, freq="W-SUN")
    snap_days = snapshots.values.astype("datetime64[D]")
    K = len(snapshots)
    hubs = list(md.REGION_HUB.values())
    configs = list(cfg["config_id"])
    h_pos = {h: i for i, h in enumerate(hubs)}
    c_pos = {c: i for i, c in enumerate(configs)}

    sold = orders[(~orders["cancelled"]) & orders["hub_arrival_date"].notna()]
    hub_idx = sold["region"].map(md.REGION_HUB).map(h_pos).values
    cfg_idx = sold["config_id"].map(c_pos).values
    qty = sold["quantity"].values

    def snapshot_index(dates):
        d = dates.values.astype("datetime64[D]")
        return np.ceil((d - snap_days[0]).astype(int) / 7).astype(int)

    inflow = np.zeros((len(hubs), len(configs), K))
    k_in = np.clip(snapshot_index(sold["hub_arrival_date"]), 0, None)
    ok = k_in < K
    np.add.at(inflow, (hub_idx[ok], cfg_idx[ok], k_in[ok]), qty[ok])

    outflow = np.zeros_like(inflow)
    delivered = sold["delivery_date"].notna().values
    k_out = np.clip(snapshot_index(sold["delivery_date"].fillna(pd.Timestamp(END))), 0, None)
    ok = delivered & (k_out < K)
    np.add.at(outflow, (hub_idx[ok], cfg_idx[ok], k_out[ok]), qty[ok])

    stock = np.cumsum(inflow, axis=2) - np.cumsum(outflow, axis=2)

    # Valid rows: config sold in the region, launched at least 2 weeks ago, not discontinued for over 90 days
    region_of_hub = {v: k for k, v in md.REGION_HUB.items()}
    valid = np.zeros_like(stock, dtype=bool)
    for h in hubs:
        for _, c in cfg.iterrows():
            if md.MODEL_MIX[region_of_hub[h]][c["model"]] == 0:
                continue
            first = c["launch_date"].to_datetime64().astype("datetime64[D]") - np.timedelta64(14, "D")
            last = np.datetime64("2100-01-01") if pd.isna(c["end_of_sale_date"]) else \
                c["end_of_sale_date"].to_datetime64().astype("datetime64[D]") + np.timedelta64(90, "D")
            valid[h_pos[h], c_pos[c["config_id"]]] = (snap_days >= first) & (snap_days <= last)

    h_i, c_i, k_i = np.nonzero(valid)
    df = pd.DataFrame({
        "source_system": "WMS",
        "snapshot_date": snapshots[k_i].strftime("%d/%m/%Y"),          # European DD/MM/YYYY format
        "warehouse_id": np.array(hubs)[h_i],
        "config_id": np.array(configs)[c_i],
        "units_in_stock": stock[h_i, c_i, k_i].astype(int),
    })

    # Defect: ~0.3% negative values (a movement recorded before receipt)
    neg = rng.choice(len(df), size=int(len(df) * 0.003), replace=False)
    df.loc[df.index[neg], "units_in_stock"] = -rng.integers(1, 4, len(neg))
    # Defect: ~1% missing rows (snapshot not reported)
    return df.drop(index=rng.choice(len(df), size=int(len(df) * 0.01), replace=False)).reset_index(drop=True)


# ======================================================================
if __name__ == "__main__":
    cfg = md.build_configs()
    customers = md.build_customers()
    salespeople = md.build_salespeople()

    orders = build_orders(get_rng(31), cfg, customers, salespeople)
    orders, capacity_nominal = simulate_production(orders, get_rng(32))
    orders = simulate_delivery(orders, get_rng(33))

    save_raw(raw_orders(orders, get_rng(41)), "crm_orders_export.csv")
    save_raw(raw_plan(orders, capacity_nominal, cfg, get_rng(42)), "erp_production_plan_export.csv")
    save_raw(raw_production(orders), "erp_production_actual_export.csv")
    save_raw(raw_stock(orders, cfg, get_rng(43)), "wms_finished_stock_export.csv")
