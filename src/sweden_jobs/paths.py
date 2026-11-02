"""File locations shared by fetch, db and analysis, relative to the project root."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADS_JSON = PROJECT_ROOT / "data" / "ads.json"
DB_PATH = PROJECT_ROOT / "data" / "jobs.duckdb"
RESULTS_DIR = PROJECT_ROOT / "results"
