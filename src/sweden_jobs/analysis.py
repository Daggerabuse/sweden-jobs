"""First analyses of the ads in data/jobs.duckdb.

Each analysis takes the ads DataFrame from load_ads_df() and returns a small
DataFrame, so the Streamlit page can reuse them. Percentages are out of all
ads in the table, except swedish_mentioned, which gives them per language.
The table keeps ads from earlier runs (see db.py), so they count too.
"""

import re
import sys

import duckdb
import pandas as pd

from sweden_jobs.paths import DB_PATH

SWEDISH_WORDS = re.compile(
    r"\b(?:och|att|är|för|med|som|vi|du|på|av|det|en|ett|har|kommer|inom)\b"
)
ENGLISH_WORDS = re.compile(
    r"\b(?:the|and|to|of|you|we|with|for|is|are|our|will|an|as)\b"
)

SWEDISH_MENTION = r"\b(?:svenska|swedish)\b"

SKILLS = {
    "Python": r"\bpython\b",
    "SQL": r"\b(?:sql|postgres(?:ql)?|mysql|mssql|sqlite)\b",
    "Java": r"\bjava\b",
    "JavaScript": r"\b(?:javascript|js)\b",
    "TypeScript": r"\btypescript\b",
    "C#": r"(?<!\w)c#",
    "C++": r"(?<!\w)c\+\+",
    ".NET": r"(?<!\w)(?:asp|vb|ado)?\.net\b|\bdotnet\b",
    "Spark": r"\bpyspark\b|(?-i:\bSpark\b)",
    "AWS": r"\baws\b",
    "Azure": r"\bazure\b",
    "GCP": r"\b(?:gcp|google cloud)\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b",
    "Linux": r"\blinux\b",
    "Power BI": r"\bpower ?bi\b",
}

# Matched against the headline, whole words, case-insensitive. "talent" alone
# is not used: it also appears in titles like "HR Product Owner for Talent".
ENTRY_LEVEL = {
    "Junior / graduate":
        r"\b(?:juniora?|graduate|trainee|ny(?:ut)?examinerad\w*|talent program(?:me)?)\b",
    "Internship": r"\b(?:praktik|praktikant(?:er)?|intern|internship)\b",
    "Summer job": r"\b(?:sommarjobb\w*|summer job|summer intern\w*)\b",
    "Student job": r"\b(?:student|studentmedarbetare)\b",
    "Thesis": r"\b(?:examensarbete\w*|thesis)\b",
}


def detect_language(text):
    """Return "sv", "en", or "unknown" (no text, or a tie)."""
    if not isinstance(text, str):
        return "unknown"
    text = text.lower()
    sv = len(SWEDISH_WORDS.findall(text))
    en = len(ENGLISH_WORDS.findall(text))
    if sv > en:
        return "sv"
    if en > sv:
        return "en"
    return "unknown"


def load_ads_df():
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        df = con.sql(
            "SELECT id, headline, description, municipality FROM ads"
        ).df()
    df["language"] = df["description"].map(detect_language)
    return df


def _percent(part, total):
    return round(100 * part / total, 1) if total else 0.0


def language_share(df):
    counts = df["language"].value_counts()
    return pd.DataFrame({
        "language": counts.index,
        "ads": counts.values,
        "percent": [_percent(n, len(df)) for n in counts.values],
    })


def swedish_mentioned(df):
    """Ads that mention "svenska" or "swedish", per ad language.

    For Swedish-language ads it adds little: an ad written in Swedish expects
    Swedish anyway, and most of them say "svenska".
    The useful number is for English ads, and it's a rough signal, not an exact
    count of Swedish requirements: "Swedish" can also mean "a Swedish company",
    and forms like "svensk"/"svenskt" are not matched (widening the pattern
    would pull in "svensk medborgare", a citizenship requirement).
    """
    mentions = df["description"].str.contains(SWEDISH_MENTION, case=False, na=False)
    grouped = mentions.groupby(df["language"]).agg(["size", "sum"])
    grouped = grouped.reindex(df["language"].value_counts().index)
    return pd.DataFrame({
        "language": grouped.index,
        "ads": grouped["size"].values,
        "mentions_swedish": grouped["sum"].values,
        "percent": [_percent(m, n) for n, m in zip(grouped["size"], grouped["sum"])],
    })


def top_cities(df, n=10):
    """Municipalities with the most ads; ads without a municipality are skipped."""
    counts = df["municipality"].value_counts().head(n)
    return pd.DataFrame({"municipality": counts.index, "ads": counts.values})


def entry_level_counts(df):
    """Entry-level ads per category, judged by the headline.

    Used instead of experience_required, which says True even for most junior
    and graduate ads and so carries no real information. An ad can fall into two
    categories (e.g. "Summer intern"); the last row counts each ad once.
    """
    rows = []
    any_match = pd.Series(False, index=df.index)
    for category, pattern in ENTRY_LEVEL.items():
        matches = df["headline"].str.contains(pattern, case=False, na=False)
        any_match |= matches
        n = int(matches.sum())
        rows.append((category, n, _percent(n, len(df))))
    n = int(any_match.sum())
    rows.append(("Any entry-level", n, _percent(n, len(df))))
    return pd.DataFrame(rows, columns=["category", "ads", "percent"])


def skill_counts(df):
    """How many ads mention each skill (each ad counts once per skill)."""
    rows = []
    for skill, pattern in SKILLS.items():
        n = int(df["description"].str.contains(pattern, case=False, na=False).sum())
        rows.append((skill, n, _percent(n, len(df))))
    result = pd.DataFrame(rows, columns=["skill", "ads", "percent"])
    return result.sort_values("ads", ascending=False, ignore_index=True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    df = load_ads_df()
    sections = [
        ("Language of the ad", language_share(df)),
        ("Mentions Swedish (svenska/swedish)", swedish_mentioned(df)),
        ("Top cities", top_cities(df)),
        ("Entry-level ads (by headline)", entry_level_counts(df)),
        ("Skills", skill_counts(df)),
    ]
    print(f"{len(df)} ads")
    for title, table in sections:
        print(f"\n== {title} ==")
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
