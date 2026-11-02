import pytest
import requests

from sweden_jobs import analysis, db, fetch


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to reach the real JobTech API."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Tests must not make real HTTP requests")

    monkeypatch.setattr(requests.Session, "send", blocked)


@pytest.fixture(autouse=True)
def isolated_data_paths(monkeypatch, tmp_path):
    """Point every data/results path at tmp_path so no test can touch the real files.

    The functions read the module constants at call time, so patching the
    constants is enough.
    """
    ads_json = tmp_path / "ads.json"
    db_path = tmp_path / "jobs.duckdb"
    results_dir = tmp_path / "results"

    monkeypatch.setattr(db, "ADS_JSON", ads_json)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(fetch, "ADS_JSON", ads_json)
    monkeypatch.setattr(analysis, "DB_PATH", db_path)
    monkeypatch.setattr(analysis, "RESULTS_DIR", results_dir)
