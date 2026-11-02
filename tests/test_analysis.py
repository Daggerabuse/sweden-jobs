import pandas as pd
import pytest

from sweden_jobs.analysis import detect_language, entry_level_counts, skill_counts


def entry_level_hits(headline):
    """Number of ads (0 or 1) that entry_level_counts finds in this headline."""
    counts = entry_level_counts(pd.DataFrame({"headline": [headline]}))
    return int(counts.set_index("category")["ads"]["Any entry-level"])


def mentions(skill, text):
    """Whether skill_counts finds this skill in a one-ad description."""
    counts = skill_counts(pd.DataFrame({"description": [text]}))
    return bool(counts.set_index("skill")["ads"][skill])


# detect_language


def test_detect_language_swedish():
    text = "Vi söker en utvecklare som har erfarenhet av Python och SQL."
    assert detect_language(text) == "sv"


def test_detect_language_english():
    text = "We are looking for a developer with experience in Python and SQL."
    assert detect_language(text) == "en"


@pytest.mark.parametrize("text", ["", "och the", "Python SQL Docker"])
def test_detect_language_tie_is_unknown(text):
    assert detect_language(text) == "unknown"


@pytest.mark.parametrize("value", [None, float("nan")])
def test_detect_language_missing_is_unknown(value):
    assert detect_language(value) == "unknown"


# ENTRY_LEVEL


@pytest.mark.parametrize(
    "headline",
    [
        "Junior Developer",
        "Juniora utvecklare",
        "Graduate Program",
        "Talent Programme",
        "Sommarjobb IT",
        "Examensarbete",
    ],
)
def test_entry_level_matches(headline):
    assert entry_level_hits(headline) == 1


@pytest.mark.parametrize(
    "headline",
    [
        "HR Product Owner for Talent",
        "Internal IT",
        "Internationellt Teknikföretag",
        "Studenter",
    ],
)
def test_entry_level_does_not_match(headline):
    assert entry_level_hits(headline) == 0


def test_entry_level_counts_ad_in_two_categories_once():
    df = pd.DataFrame({"headline": ["Summer intern", "Senior Developer", None]})
    counts = entry_level_counts(df).set_index("category")["ads"]
    assert counts["Internship"] == 1
    assert counts["Summer job"] == 1
    assert counts["Any entry-level"] == 1


# SKILLS


@pytest.mark.parametrize(
    ("text", "skill", "expected"),
    [
        ("Experience with JavaScript", "JavaScript", True),
        ("Experience with JavaScript", "Java", False),
        ("Experience with Java", "Java", True),
        ("Node.js and React", "JavaScript", True),
        ("Read more at www.site.net", ".NET", False),
        ("Built on .NET", ".NET", True),
        ("ASP.NET Core", ".NET", True),
        ("dotnet developer", ".NET", True),
        ("C# and C++", "C#", True),
        ("C# and C++", "C++", True),
        ("PostgreSQL databases", "SQL", True),
        ("PySpark pipelines", "Spark", True),
        ("Apache Spark", "Spark", True),
        ("a spark of creativity", "Spark", False),
        ("Power BI reports", "Power BI", True),
        ("PowerBI reports", "Power BI", True),
        ("Google Cloud Platform", "GCP", True),
        ("pythonic", "Python", False),
    ],
)
def test_skill_patterns(text, skill, expected):
    assert mentions(skill, text) is expected
