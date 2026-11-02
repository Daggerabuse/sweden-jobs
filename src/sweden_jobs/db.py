"""Load data/ads.json into the DuckDB table `ads` (data/jobs.duckdb).

Each run upserts: ads with a new id are added, ads already in the table are
updated with the latest data, and nothing is ever deleted. Ads that have since
expired stay in the table, so `ads` holds every ad seen across all runs.

first_seen / last_seen (UTC) record the run in which an ad was first and most
recently seen. first_seen is set on insert and never changed; last_seen is
updated on every run the ad is still in the API. Ads stored before these
columns existed have first_seen NULL (seen before tracking started)."""

import json
import sys
from datetime import UTC, datetime

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
# first_seen is left out of the SET list, so an existing ad keeps it.
_UPDATES = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "id")
INSERT_SQL = f"""
    INSERT INTO ads ({_COLS}, first_seen, last_seen)
    SELECT {_COLS}, seen_at, seen_at FROM new_ads
    ON CONFLICT (id) DO UPDATE SET {_UPDATES}, last_seen = excluded.last_seen
"""


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
            employment_type     VARCHAR,
            first_seen          TIMESTAMP,
            last_seen           TIMESTAMP
        )
    """)
    # Tables created before these columns existed get them added here.
    con.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS first_seen TIMESTAMP")
    con.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP")


def load_ads(path=ADS_JSON):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def upsert_ads(con, ads, seen_at=None):
    """Insert new ads and update existing ones (matched by id); ads not in
    this batch are left as they are. It is a single INSERT statement, so if it
    fails nothing is written. An ad without an id is rejected by the PRIMARY
    KEY. seen_at (naive UTC, default now) becomes last_seen for every ad in
    the batch, and first_seen for new ones."""
    create_table(con)
    if seen_at is None:
        seen_at = datetime.now(UTC).replace(tzinfo=None)
    rows = [tuple(ad[c] for c in COLUMNS) for ad in ads]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["seen_at"] = pd.Series([seen_at] * len(df), dtype="datetime64[us]")
    con.register("new_ads", df)
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
