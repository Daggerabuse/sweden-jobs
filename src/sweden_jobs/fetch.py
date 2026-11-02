"""Fetch Data/IT job ads from the JobTech search API and save them to data/ads.json."""

import json
import os
import tempfile
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sweden_jobs.paths import ADS_JSON

URL = "https://jobsearch.api.jobtechdev.se/search"
OCCUPATION_FIELD = "apaJ_2ja_LuF"  # Data/IT
LIMIT = 100
MAX_OFFSET = 2000
SLEEP_SECONDS = 0.5


def make_session():
    """Session that reuses one connection and retries 429/5xx with backoff."""
    retry = Retry(
        total=3,
        backoff_factor=1,  # waits 0s, 2s, 4s (urllib3 skips the first sleep)
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["accept"] = "application/json"
    return session


def fetch_page(session, offset):
    params = {
        "occupation-field": OCCUPATION_FIELD,
        "limit": LIMIT,
        "offset": offset,
        "sort": "pubdate-desc",
    }
    response = session.get(URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected API response, not an object: {str(data)[:300]}")
    return data


def fetch_all(session):
    all_ads = []
    offset = 0
    total = None
    hit_cap = False

    while True:
        data = fetch_page(session, offset)
        hits = data.get("hits") or []

        if total is None:
            try:
                total = data["total"]["value"]
            except KeyError, TypeError:
                raise RuntimeError(
                    f"Unexpected API response, no total.value: {str(data)[:300]}"
                ) from None
            print(total, len(hits))

        if not hits:
            break

        all_ads.extend(hits)
        print(offset, len(all_ads))

        offset += LIMIT
        if offset >= total:
            break
        if offset > MAX_OFFSET:
            hit_cap = True
            break

        time.sleep(SLEEP_SECONDS)

    ads = dedupe(all_ads)
    if len(ads) < total:
        reason = "API offset cap" if hit_cap else "results shifted or ended early"
        print(f"WARNING: got {len(ads)} of {total} ads ({reason})")
    return ads


def dedupe(ads):
    """Drop repeated ids (ads can shift between pages while we crawl) and ads
    without an id, which can't be stored in the id-keyed database."""
    seen = set()
    unique = []
    no_id = 0
    for ad in ads:
        ad_id = ad.get("id")
        if ad_id is None:
            no_id += 1
        elif ad_id not in seen:
            seen.add(ad_id)
            unique.append(ad)
    if no_id:
        print(f"WARNING: dropped {no_id} ads without an id")
    duplicates = len(ads) - len(unique) - no_id
    if duplicates:
        print(f"Removed {duplicates} duplicate ads")
    return unique


def _get(d, *keys):
    """Walk nested dicts; return None if any level is missing or None."""
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def clean_ad(ad):
    return {
        "id": _get(ad, "id"),
        "headline": _get(ad, "headline"),
        "employer": _get(ad, "employer", "name"),
        "municipality": _get(ad, "workplace_address", "municipality"),
        "publication_date": _get(ad, "publication_date"),
        "description": _get(ad, "description", "text"),
        "experience_required": _get(ad, "experience_required"),
        "occupation": _get(ad, "occupation", "label"),
        "employment_type": _get(ad, "employment_type", "label"),
    }


def save(ads, path=None):
    """Write to a temp file first, then swap it in, so a crash never leaves
    a half-written ads.json."""
    if path is None:
        path = ADS_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(ads, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main():
    with make_session() as session:
        raw_ads = fetch_all(session)
    ads = [clean_ad(ad) for ad in raw_ads]
    save(ads)
    print(f"{len(ads)} ads saved to {ADS_JSON}")


if __name__ == "__main__":
    main()
