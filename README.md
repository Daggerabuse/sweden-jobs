# sweden-jobs
[![CI](https://github.com/Daggerabuse/sweden-jobs/actions/workflows/ci.yml/badge.svg)](https://github.com/Daggerabuse/sweden-jobs/actions/workflows/ci.yml)

**Live dashboard:** [sweden-jobs.streamlit.app](https://sweden-jobs.streamlit.app/)

A data pipeline that collects IT job ads in Sweden from the Swedish Public Employment Service's [JobTech API](https://jobtechdev.se/en/components/jobsearch) and analyses what the market asks for: language, skills, locations and entry-level opportunities.

## Why

When I moved to Italy to study, Sweden was not part of my plan; I was thinking about other countries. Through friendships I made here, I became interested in Sweden, and my university turned out to offer ways to do my master's at good Swedish universities. The more I looked at the country, the more I liked its culture. Take fika: it happens everywhere, at school, at work, around anything, and if you turn one down, people look at you like you've committed a crime.

So I started this project with one question: *as a first-year student, could I find a job in Sweden?* I partly found the answer. I was surprised that 73% of IT ads are written in Swedish; I expected far more English. It didn't change my decision, though: I still want an internship in Sweden next summer, and I believe I can get one.

## Key findings

Snapshot of 2,100 Data/IT ads on Platsbanken, collected on 2 November 2026. These numbers stay fixed; the [live dashboard](https://sweden-jobs.streamlit.app/) shows the current figures.

**Language**
- **73%** of ads are written in Swedish, 27% in English.
- 29% of the English ads still mention Swedish ("svenska" or "Swedish").
- That leaves **about 19% of all ads** (≈400) written in English without mentioning Swedish: roughly one in five ads looks open to someone who doesn't speak Swedish. This is an upper bound, since some English ads expect Swedish without saying so.

**Skills** (share of ads mentioning each)

| Skill | Ads | Share |
|---|---|---|
| Python | 375 | 17.9% |
| Azure | 361 | 17.2% |
| SQL | 297 | 14.1% |
| Linux | 280 | 13.3% |
| Kubernetes | 224 | 10.7% |
| Java | 220 | 10.5% |
| AWS | 172 | 8.2% |

Azure is mentioned **twice as often as AWS**: the Swedish market leans on Microsoft. The shares look low because "Data/IT" is a broad field that also covers support, operations and testing roles.

**Locations:** Stockholm has 31% of the ads, Göteborg 16% and Linköping 7%.

**Entry level:** only **55 ads (2.6%)** are entry level by their headline, and 47 of those are junior or graduate roles. No summer jobs are posted yet; in Sweden they are usually published between January and March.

## How it works

```mermaid
flowchart LR
    A[JobTech API] -->|fetch.py| B[data/ads.json]
    B -->|db.py| C[(DuckDB<br/>data/jobs.duckdb)]
    C -->|analysis.py| D[results/*.csv]
    D -->|commit to master| E[Streamlit dashboard]
    C -.->|force-push, single commit| F[data branch]
    F -.->|restored at the start of each run| C
```

- **`fetch.py`** pages through the API's Data/IT ads, newest first, with retries and back-off. It removes duplicate ads (ads can shift between pages during a crawl) and writes the result atomically, so a crash never leaves a half-written file.
- **`db.py`** upserts the ads into DuckDB. Nothing is deleted, so ads accumulate across runs and expired ads stay available for trend analysis.
- **`analysis.py`** detects each ad's language, checks for Swedish requirements, and counts skills, cities and entry-level ads. It writes the results to `results/`.

### Daily automation

A GitHub Actions workflow (`.github/workflows/daily.yml`) runs every day at 05:17 UTC, and can also be started by hand. Each run:

1. restores `jobs.duckdb` from the `data` branch,
2. runs fetch → db → analysis,
3. force-pushes the updated database back to the `data` branch as a single commit, so the repository doesn't collect a new copy of the binary file every day,
4. commits `results/` to master as "Update results (YYYY-MM-DD)" if anything changed.

The Streamlit dashboard reads only `results/`, so it updates by itself after that commit.

### `first_seen` and `last_seen`

Each ad has two UTC timestamps. `first_seen` is the run in which the ad first appeared and is never changed afterwards. `last_seen` is updated on every run in which the ad is still in the API. An ad whose `last_seen` stops moving has closed or expired. Ads collected before tracking started (before 2 November 2026) have an empty `first_seen`, because their first appearance is unknown.

## Limitations

- **API cap:** the search API stops answering after offset 2000, so one run collects at most 2,100 ads (out of 2,501 on 2 November). Because ads are sorted newest first, the oldest ads are the ones missed. The daily run accumulates ads in the database, so ads missed one day are usually caught on a later day while they are still among the newest, and the gap closes over time. Ads that were already past the cap before the first run stay missed.
- **`experience_required` is unreliable:** it says "experience required" even for most junior and graduate ads, including every Volvo Group Graduate Program ad. Entry-level ads are therefore detected from the headline instead.
- **Language detection is word-based:** it compares common Swedish and English words, so ads that mix both languages are labelled by whichever part is longer. "Swedish" can also mean "a Swedish company", which slightly inflates the Swedish-requirement count for English ads.
- **Platsbanken is not the whole market:** many large companies post graduate programmes and internships only on their own career sites or LinkedIn, so entry-level opportunities are likely undercounted.
- **Source texts:** a few ads are cut off in the source itself. The search API does not shorten texts (checked against the full ads from `/ad/{id}`), but incomplete ads can lower the shares slightly.

## How to run

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Daggerabuse/sweden-jobs.git
cd sweden-jobs
uv sync

uv run python -m sweden_jobs.fetch      # download ads to data/ads.json
uv run python -m sweden_jobs.db         # load them into data/jobs.duckdb
uv run python -m sweden_jobs.analysis   # print the findings
```

### Running tests

`uv sync` also installs the dev tools (pytest, ruff). Then:

```bash
uv run pytest        # run the tests
uv run ruff check    # lint
```

The tests never call the real API or touch `data/`: database tests use a temporary DuckDB file. CI runs both commands on every push to master made by a person and on every pull request (the daily bot's pushes use `GITHUB_TOKEN`, which doesn't trigger workflows) (`.github/workflows/ci.yml`).

## Roadmap

- ~~**Automation:** daily GitHub Actions run, `first_seen` / `last_seen` per ad.~~ Done.
- ~~**Tests and CI:** automated tests, run on every push.~~ Done.
- **Open vs. closed ads:** use `last_seen` to tell which ads are still open and how long ads stay up.
- **Trend charts:** show how skills, languages and entry-level shares change over time.
- **Beyond the 2,000 cap:** split queries by publication date to collect every ad.
- **NLP:** better language detection, skill extraction beyond keyword lists, and clustering ads to see how many different jobs hide behind one title.