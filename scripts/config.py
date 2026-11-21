from pathlib import Path
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"
RANDOM_SEED = 42
ERP_MIGRATION_DATE = "2025-07-01"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
CURATED_DIR = PROJECT_ROOT / "data" / "curated"