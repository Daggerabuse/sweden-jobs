"""Load data/ads.json into the DuckDB table `ads` (data/jobs.duckdb).

Each run upserts: ads with a new id are added, ads already in the table are
updated with the latest data, and nothing is ever deleted. Ads that have since
expired stay in the table, so `ads` holds every ad seen across all runs."""

import json
import sys

import duckdb
import pandas as pd

from sweden_jobs.paths import ADS_JSON, DB_PATH

COLUMNS = (
    "id",
    "headline",
    "employer",
    "municipality",
    "publication_date",
    "description",
    "experience_required",
    "occupation",
    "employment_type",
)

_COLS = ", ".join(COLUMNS)
INSERT_SQL = f"INSERT OR REPLACE INTO ads ({_COLS}) SELECT {_COLS} FROM new_ads"


def create_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id                  VARCHAR PRIMARY KEY,
            headline            VARCHAR,
            employer            VARCHAR,
            municipality        VARCHAR,
            publication_date    TIMESTAMP,
            description         VARCHAR,
            experience_required BOOLEAN,
            occupation          VARCHAR,
            employment_type     VARCHAR
        )
    """)


def load_ads(path=ADS_JSON):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def upsert_ads(con, ads):
    """Insert new ads and update existing ones (matched by id); ads not in
    this batch are left as they are. It is a single INSERT statement, so if it
    fails nothing is written. An ad without an id is rejected by the PRIMARY
    KEY."""
    create_table(con)
    rows = [tuple(ad[c] for c in COLUMNS) for ad in ads]
    con.register("new_ads", pd.DataFrame(rows, columns=COLUMNS))
    try:
        con.execute(INSERT_SQL)
    finally:
        con.unregister("new_ads")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ads = load_ads()
    with duckdb.connect(str(DB_PATH)) as con:
        upsert_ads(con, ads)
        print(con.sql("SELECT COUNT(*) FROM ads"))
        print(con.sql(
            "SELECT headline, employer, municipality FROM ads "
            "ORDER BY publication_date DESC LIMIT 5"
        ))


if __name__ == "__main__":
    main()
