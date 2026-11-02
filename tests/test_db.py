from datetime import datetime

import duckdb
import pytest

from sweden_jobs.db import COLUMNS, upsert_ads

T1 = datetime(2026, 1, 1, 5, 17)
T2 = datetime(2026, 1, 2, 5, 17)


def make_ad(ad_id, headline="Developer"):
    ad = dict.fromkeys(COLUMNS)
    ad.update(
        id=ad_id,
        headline=headline,
        employer="Acme AB",
        municipality="Stockholm",
        publication_date="2026-01-01T08:00:00",
        description="Vi söker en utvecklare.",
        experience_required=True,
    )
    return ad


@pytest.fixture
def con(tmp_path):
    with duckdb.connect(str(tmp_path / "test.duckdb")) as con:
        yield con


def rows(con):
    return {
        row[0]: row[1:]
        for row in con.execute("SELECT id, headline, first_seen, last_seen FROM ads").fetchall()
    }


def test_upsert_same_ad_twice(con):
    upsert_ads(con, [make_ad("1", "Developer")], seen_at=T1)
    upsert_ads(con, [make_ad("1", "Senior Developer")], seen_at=T2)

    assert rows(con) == {"1": ("Senior Developer", T1, T2)}


def test_upsert_leaves_missing_ads_and_adds_new_ones(con):
    upsert_ads(con, [make_ad("1"), make_ad("2")], seen_at=T1)
    upsert_ads(con, [make_ad("2"), make_ad("3")], seen_at=T2)

    result = rows(con)
    assert len(result) == 3
    assert result["1"][1:] == (T1, T1)  # not in the second batch: untouched
    assert result["2"][1:] == (T1, T2)
    assert result["3"][1:] == (T2, T2)


def test_upsert_rejects_ad_without_id(con):
    with pytest.raises(duckdb.ConstraintException):
        upsert_ads(con, [make_ad("1"), make_ad(None)], seen_at=T1)
    # One INSERT statement, so nothing from the batch is written.
    assert con.execute("SELECT COUNT(*) FROM ads").fetchone()[0] == 0
