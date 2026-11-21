"""
raw_common.py
-------------
Small helper functions shared by every RAW generation script.

Two families:
1. Technical tools: a reproducible random generator, CSV saving.
2. "Mess" tools: they deliberately damage clean data so that the Raw
   layer looks like a real export from a source system.
   Every injected defect is listed in docs/data_quality_issues.md.
"""
import os

import numpy as np
import pandas as pd

from config import RANDOM_SEED, RAW_DIR


def get_rng(offset=0):
    """Reproducible random generator.

    Same seed => same data on every run. The offset gives each step its
    own random stream: changing one step doesn't change the others.
    """
    return np.random.default_rng(RANDOM_SEED + offset)


def save_raw(df, filename):
    """Write a DataFrame to data/raw as CSV (UTF-8, no index column)."""
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"Saved: {path} ({len(df)} rows)")


# ----------------------------------------------------------------------
# Mess tools
# ----------------------------------------------------------------------
def mess_text(series, rng, share=0.05):
    """Inconsistent casing and stray whitespace on a share of text values.

    Example: 'Comfort' -> 'COMFORT', 'comfort' or ' Comfort '.
    """
    out = series.astype(object).copy()
    n = int(len(out) * share)
    if n == 0:
        return out
    positions = rng.choice(len(out), size=n, replace=False)
    kinds = rng.integers(0, 3, size=n)
    for pos, kind in zip(positions, kinds):
        value = out.iloc[pos]
        if isinstance(value, str):
            if kind == 0:
                out.iloc[pos] = value.upper()
            elif kind == 1:
                out.iloc[pos] = value.lower()
            else:
                out.iloc[pos] = f" {value} "
    return out


def set_nulls(series, rng, share=0.02):
    """Replace a share of values with blanks (missing values)."""
    out = series.astype(object).copy()
    n = int(len(out) * share)
    if n == 0:
        return out
    positions = rng.choice(len(out), size=n, replace=False)
    out.iloc[positions] = np.nan
    return out


def add_duplicates(df, rng, share=0.005):
    """Add exact duplicate rows, inserted right after the original row.

    Simulates a double click, a double load, or a re-run export.
    """
    n = int(len(df) * share)
    if n == 0:
        return df.reset_index(drop=True)
    positions = rng.choice(len(df), size=n, replace=False)
    duplicates = df.iloc[positions]
    out = pd.concat([df, duplicates]).sort_index(kind="stable")
    return out.reset_index(drop=True)
