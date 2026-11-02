"""Streamlit page with the findings. Reads only the files in results/, which
`python -m sweden_jobs.analysis` writes, so it needs no database or API."""

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RESULTS_DIR = Path(__file__).resolve().parent / "results"
GITHUB_URL = "https://github.com/Daggerabuse/sweden-jobs"
LINKEDIN_URL = "https://www.linkedin.com/in/mete-cem-bulut"

# One series per chart, so one hue; the dark step is brighter for the dark surface.
BAR_COLOR = {"light": "#2a78d6", "dark": "#3987e5"}


# Not cached: reading these small files takes milliseconds, and st.cache_data
# would keep serving old numbers after results/ is rewritten.
def load_results():
    tables = {
        path.stem: pd.read_csv(path, encoding="utf-8")
        for path in RESULTS_DIR.glob("*.csv")
    }
    meta = json.loads((RESULTS_DIR / "meta.json").read_text(encoding="utf-8"))
    return tables, meta


def format_percent(ads, percent):
    """Percent as text: a real 0 stays "0", but a few ads that round to 0.0
    are shown as "<0.1" so they don't look like none."""
    if ads == 0:
        return "0"
    if percent < 0.1:
        return "<0.1"
    return f"{percent:.1f}"


def bar_chart(table, category, title):
    """Horizontal bars of % of all ads, longest first, with a hover tooltip
    and a table view."""
    theme = st.context.theme.type or "light"
    chart = (
        alt.Chart(table)
        .mark_bar(color=BAR_COLOR[theme], cornerRadiusEnd=4, size=18)
        .encode(
            x=alt.X("percent:Q", title="% of all ads"),
            y=alt.Y(f"{category}:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=title),
                alt.Tooltip("percent:Q", title="% of all ads", format=".1f"),
                alt.Tooltip("ads:Q", title="Ads"),
            ],
        )
        .properties(height=28 * len(table))
    )
    st.altair_chart(chart, width="stretch")
    with st.expander("Show table"):
        st.dataframe(table, hide_index=True, width="stretch")


st.set_page_config(page_title="IT jobs in Sweden", layout="centered")
tables, meta = load_results()

st.title("IT jobs in Sweden")
st.markdown(
    "Built by Mete Cem Bulut, a Computer Engineering student at Politecnico di "
    "Torino, to find out whether a first-year student can find work in Sweden."
)
st.caption(
    f"{meta['ads']:,} Data/IT ads from Platsbanken (JobTech API) collected so "
    f"far, newest published {meta['data_date']}"
)

# Language
st.header("Language")
language = tables["language"].set_index("language")
english = tables["swedish_mentioned"].set_index("language").loc["en"]
# English ads that don't mention Swedish, as a share of all ads.
open_ads = int(english["ads"] - english["mentions_swedish"])
open_share = 100 * open_ads / meta["ads"]

col1, col2, col3 = st.columns(3)
col1.metric("Written in Swedish", f"{language.loc['sv', 'percent']:.0f}%")
col2.metric("Written in English", f"{language.loc['en', 'percent']:.0f}%")
col3.metric(
    "Of English ads: mention Swedish",
    f"{english['percent']:.0f}%",
    help=f"{int(english['mentions_swedish'])} of {int(english['ads'])} English ads "
    'say "svenska" or "Swedish".',
)
st.info(
    f"**About {open_share:.0f}% of all ads (≈{open_ads}) may not require "
    "Swedish:** they are written in English and don't mention Swedish. "
    "This is an upper bound, since some English ads expect Swedish without "
    "saying so."
)

# Skills
st.header("Skills")
st.caption("Share of ads that mention each skill in their description.")
skills = tables["skills"].set_index("skill")["ads"]
# The more-mentioned cloud goes first, so the sentence reads right either way.
more, less = sorted(["Azure", "AWS"], key=lambda s: skills[s], reverse=True)
if skills[less] > 0:
    st.markdown(
        f"{more} is mentioned **{skills[more] / skills[less]:.1f}× as often** "
        f"as {less} ({skills[more]} vs {skills[less]} ads)."
    )
bar_chart(tables["skills"], "skill", "Skill")

# Cities
st.header("Top 10 cities")
bar_chart(tables["top_cities"], "municipality", "City")

# Entry level
st.header("Entry-level ads")
entry = tables["entry_level"]
total = entry[entry["category"] == "Any entry-level"].iloc[0]
st.metric(
    "Entry-level ads, by headline",
    f"{int(total['ads'])}",
    help=f"{total['percent']:.1f}% of all ads. An ad can be in two categories, "
    "so the categories can add up to more than this.",
)
# A table, not a chart: junior/graduate dwarfs the other categories, so their
# bars would be too small to read.
categories = entry[entry["category"] != "Any entry-level"]
st.dataframe(
    pd.DataFrame({
        "Category": categories["category"],
        "Ads": categories["ads"],
        "% of all ads": [
            format_percent(a, p)
            for a, p in zip(categories["ads"], categories["percent"])
        ],
    }),
    hide_index=True,
    width="stretch",
)

# Limitations
st.header("Limitations")
st.markdown(
    """
- **API cap:** the search API stops after offset 2000, so one run collects at
  most 2,100 ads. Ads are sorted newest first, so the oldest ones are missed.
- **`experience_required` is unreliable:** it says "experience required" even
  for most junior and graduate ads, so entry-level ads are found by headline.
- **Language detection is word-based:** mixed-language ads get the label of
  their longer part, and "Swedish" can also mean "a Swedish company".
- **Platsbanken is not the whole market:** many companies post graduate
  programmes and internships only on their own sites or LinkedIn.
- **Source texts:** a few ads are cut off in the source itself, which can
  lower the shares slightly.
"""
)
st.markdown(
    f"Code and method: [{GITHUB_URL.removeprefix('https://')}]({GITHUB_URL})"
    f" · LinkedIn: [{LINKEDIN_URL.removeprefix('https://www.')}]({LINKEDIN_URL})"
)
