import pytest

from sweden_jobs import fetch
from sweden_jobs.fetch import _get, clean_ad, dedupe

FULL_AD = {
    "id": "123",
    "headline": "Junior Developer",
    "employer": {"name": "Acme AB"},
    "workplace_address": {"municipality": "Stockholm"},
    "publication_date": "2026-11-01T08:00:00",
    "description": {"text": "Vi söker en utvecklare."},
    "experience_required": False,
    "occupation": {"label": "Mjukvaruutvecklare"},
    "employment_type": {"label": "Vanlig anställning"},
}

CLEAN_KEYS = {
    "id",
    "headline",
    "employer",
    "municipality",
    "publication_date",
    "description",
    "experience_required",
    "occupation",
    "employment_type",
}


# _get


def test_get_nested():
    assert _get({"a": {"b": {"c": 1}}}, "a", "b", "c") == 1


def test_get_missing_key():
    assert _get({"a": {}}, "a", "b") is None
    assert _get({}, "a", "b") is None


def test_get_none_in_the_middle():
    assert _get({"a": None}, "a", "b") is None


def test_get_non_dict_in_the_middle():
    assert _get({"a": "text"}, "a", "b") is None
    assert _get({"a": ["list"]}, "a", "b") is None


def test_get_non_dict_root():
    assert _get(None, "a") is None


def test_get_keeps_falsy_values():
    assert _get({"a": False}, "a") is False
    assert _get({"a": 0}, "a") == 0


# clean_ad


def test_clean_ad_full():
    assert clean_ad(FULL_AD) == {
        "id": "123",
        "headline": "Junior Developer",
        "employer": "Acme AB",
        "municipality": "Stockholm",
        "publication_date": "2026-11-01T08:00:00",
        "description": "Vi söker en utvecklare.",
        "experience_required": False,
        "occupation": "Mjukvaruutvecklare",
        "employment_type": "Vanlig anställning",
    }


def test_clean_ad_empty():
    cleaned = clean_ad({})
    assert set(cleaned) == CLEAN_KEYS
    assert all(value is None for value in cleaned.values())


def test_clean_ad_none_and_malformed_fields():
    ad = {
        "id": "1",
        "headline": None,
        "employer": None,
        "workplace_address": {},
        "description": "plain text instead of an object",
        "occupation": {"label": None},
        "employment_type": [],
    }
    cleaned = clean_ad(ad)
    assert set(cleaned) == CLEAN_KEYS
    assert cleaned["id"] == "1"
    assert all(value is None for key, value in cleaned.items() if key != "id")


# dedupe


def test_dedupe_keeps_first_of_repeated_id(capsys):
    ads = [
        {"id": "1", "headline": "first"},
        {"id": "2", "headline": "other"},
        {"id": "1", "headline": "second"},
    ]
    result = dedupe(ads)
    assert result == [ads[0], ads[1]]
    assert "Removed 1 duplicate ads" in capsys.readouterr().out


def test_dedupe_drops_ads_without_id(capsys):
    # Ads without an id can't go into the id-keyed database, so they are dropped.
    ads = [{"id": "1"}, {"headline": "no id"}, {"id": None}]
    result = dedupe(ads)
    assert result == [{"id": "1"}]
    out = capsys.readouterr().out
    assert "dropped 2 ads without an id" in out
    assert "duplicate" not in out


def test_dedupe_no_changes_prints_nothing(capsys):
    ads = [{"id": "1"}, {"id": "2"}]
    assert dedupe(ads) == ads
    assert capsys.readouterr().out == ""


# fetch_all


class FakeSession:
    """Stands in for requests.Session: serves pages from a list of hit-lists."""

    def __init__(self, pages, total):
        self.pages = pages
        self.total = total
        self.offsets = []

    def get(self, url, params, timeout):
        offset = params["offset"]
        self.offsets.append(offset)
        index = offset // fetch.LIMIT
        hits = self.pages[index] if index < len(self.pages) else []
        return FakeResponse({"total": {"value": self.total}, "hits": hits})


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def make_hits(start, count):
    return [{"id": str(i)} for i in range(start, start + count)]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)


def test_fetch_all_stops_when_total_reached(monkeypatch):
    monkeypatch.setattr(fetch, "LIMIT", 2)
    session = FakeSession([make_hits(0, 2), make_hits(2, 1)], total=3)
    ads = fetch.fetch_all(session)
    assert [ad["id"] for ad in ads] == ["0", "1", "2"]
    assert session.offsets == [0, 2]


def test_fetch_all_stops_on_empty_page_and_warns(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "LIMIT", 2)
    session = FakeSession([make_hits(0, 2)], total=10)
    ads = fetch.fetch_all(session)
    assert len(ads) == 2
    assert session.offsets == [0, 2]
    assert "results shifted or ended early" in capsys.readouterr().out


def test_fetch_all_stops_at_max_offset_and_warns(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "LIMIT", 2)
    monkeypatch.setattr(fetch, "MAX_OFFSET", 4)
    pages = [make_hits(i * 2, 2) for i in range(10)]
    session = FakeSession(pages, total=20)
    ads = fetch.fetch_all(session)
    assert session.offsets == [0, 2, 4]
    assert len(ads) == 6
    assert "API offset cap" in capsys.readouterr().out


def test_fetch_all_without_total_raises():
    class NoTotal(FakeSession):
        def get(self, url, params, timeout):
            return FakeResponse({"hits": []})

    with pytest.raises(RuntimeError, match="no total.value"):
        fetch.fetch_all(NoTotal([], total=0))
