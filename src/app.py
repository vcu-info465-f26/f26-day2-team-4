import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from build_db import build
build()

DB_PATH = Path(__file__).resolve().parents[1] / "project.db"

st.set_page_config(page_title="Listen Count Dashboard", layout="wide")


@st.cache_data
def load_data(database_path):
    with sqlite3.connect(database_path) as connection:
        artists = pd.read_sql_query(
            "SELECT snapshot_date, artist_mbid, artist_name, listen_count FROM artist_stats",
            connection,
        )
        releases = pd.read_sql_query(
            "SELECT snapshot_date, release_mbid, release_name, artist_name, listen_count FROM release_stats",
            connection,
        )

    artists["snapshot_date"] = pd.to_datetime(artists["snapshot_date"])
    releases["snapshot_date"] = pd.to_datetime(releases["snapshot_date"])
    return artists, releases


def get_date_bounds(dataframes):
    dates = pd.concat(
        [frame["snapshot_date"] for frame in dataframes if not frame.empty],
        ignore_index=True,
    )
    return dates.min().date(), dates.max().date()


def filter_by_date(frame, start_date, end_date):
    return frame[
        (frame["snapshot_date"] >= start_date) & (frame["snapshot_date"] <= end_date)
    ].copy()


def build_label_map(frame, key_field, label_format):
    options = frame.drop_duplicates(key_field).sort_values("listen_count", ascending=False)
    return {label_format(row): getattr(row, key_field) for row in options.itertuples()}


st.title("Listen Count Dashboard")

if not DB_PATH.is_file():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()

try:
    artist_data, release_data = load_data(str(DB_PATH))
except sqlite3.Error as error:
    st.error(f"Could not read ListenBrainz data from {DB_PATH}: {error}")
    st.stop()

if artist_data.empty and release_data.empty:
    st.warning("The database has no listen-count snapshots yet.")
    st.stop()

min_date, max_date = get_date_bounds((artist_data, release_data))

st.sidebar.header("Filters")
selected_date_range = st.sidebar.date_input(
    "Snapshot date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if not isinstance(selected_date_range, tuple) or len(selected_date_range) != 2:
    st.info("Select both a start date and an end date.")
    st.stop()

start_date, end_date = pd.to_datetime(selected_date_range)
artists = filter_by_date(artist_data, start_date, end_date)
releases = filter_by_date(release_data, start_date, end_date)

st.sidebar.divider()

if artists.empty and releases.empty:
    st.info("No snapshots match the selected date range.")
    st.stop()

latest_date = max(
    [frame["snapshot_date"].max() for frame in (artists, releases) if not frame.empty]
)
latest_artists = artists[artists["snapshot_date"] == latest_date]
latest_releases = releases[releases["snapshot_date"] == latest_date]

artist_labels = build_label_map(
    latest_artists,
    "artist_mbid",
    lambda row: f"{row.artist_name} [{row.artist_mbid[:8]}]",
)
release_labels = build_label_map(
    latest_releases,
    "release_mbid",
    lambda row: f"{row.release_name} - {row.artist_name} [{row.release_mbid[:8]}]",
)

st.sidebar.subheader("Chart series")
selected_artists = st.sidebar.multiselect(
    "Artists",
    options=list(artist_labels),
    default=list(artist_labels)[:8],
)
selected_releases = st.sidebar.multiselect(
    "Releases",
    options=list(release_labels),
    default=list(release_labels)[:8],
)
artist_ids = [artist_labels[label] for label in selected_artists]
release_ids = [release_labels[label] for label in selected_releases]

album_tab, artist_tab, both_tab = st.tabs(["Albums", "Artists", "Both"])

with album_tab:
    release_trend = releases[releases["release_mbid"].isin(release_ids)].copy()
    if release_trend.empty:
        st.subheader("Release listens over time")
        st.info("Select one or more releases to show this chart.")
    else:
        release_trend["series"] = release_trend["release_name"] + " - " + release_trend["artist_name"]
        fig = px.line(
            release_trend,
            x="snapshot_date",
            y="listen_count",
            color="series",
            markers=True,
            hover_data=["release_mbid"],
            labels={
                "snapshot_date": "Snapshot date",
                "listen_count": "Listens",
                "series": "Release",
            },
        )
        st.subheader("Release listens over time")
        st.plotly_chart(fig, width="stretch")
        st.subheader("Chart data")
        st.dataframe(
            release_trend[
                ["snapshot_date", "release_name", "artist_name", "listen_count", "release_mbid"]
            ].rename(
                columns={
                    "snapshot_date": "Snapshot date",
                    "release_name": "Album",
                    "artist_name": "Artist",
                    "listen_count": "Listens",
                    "release_mbid": "Release MBID",
                }
            ),
            width="stretch",
            hide_index=True,
        )

with artist_tab:
    artist_trend = artists[artists["artist_mbid"].isin(artist_ids)].copy()
    if artist_trend.empty:
        st.subheader("Artist listens over time")
        st.info("Select one or more artists to show this chart.")
    else:
        fig = px.line(
            artist_trend,
            x="snapshot_date",
            y="listen_count",
            color="artist_name",
            markers=True,
            hover_data=["artist_mbid"],
            labels={
                "snapshot_date": "Snapshot date",
                "listen_count": "Listens",
                "artist_name": "Artist",
            },
        )
        st.subheader("Artist listens over time")
        st.plotly_chart(fig, width="stretch")
        st.subheader("Chart data")
        st.dataframe(
            artist_trend[
                ["snapshot_date", "artist_name", "listen_count", "artist_mbid"]
            ].rename(
                columns={
                    "snapshot_date": "Snapshot date",
                    "artist_name": "Artist",
                    "listen_count": "Listens",
                    "artist_mbid": "Artist MBID",
                }
            ),
            width="stretch",
            hide_index=True,
        )

with both_tab:
    st.subheader("Artist and release listens over time")
    combined_series = []
    if artist_ids:
        artist_series = artists[artists["artist_mbid"].isin(artist_ids)].copy()
        artist_series["series"] = "Artist: " + artist_series["artist_name"]
        artist_series["series_type"] = "Artist"
        combined_series.append(
            artist_series[["snapshot_date", "series", "series_type", "listen_count"]]
        )
    if release_ids:
        release_series = releases[releases["release_mbid"].isin(release_ids)].copy()
        release_series["series"] = "Release: " + release_series["release_name"] + " - " + release_series["artist_name"]
        release_series["series_type"] = "Release"
        combined_series.append(
            release_series[["snapshot_date", "series", "series_type", "listen_count"]]
        )

    if not combined_series:
        st.info("Select artists or releases to show the combined chart.")
    else:
        combined_trend = pd.concat(combined_series, ignore_index=True)
        fig = px.line(
            combined_trend,
            x="snapshot_date",
            y="listen_count",
            color="series",
            line_dash="series_type",
            markers=True,
            labels={
                "snapshot_date": "Snapshot date",
                "listen_count": "Listens",
                "series": "Artist or release",
                "series_type": "Type",
            },
        )
        st.plotly_chart(fig, width="stretch")
        st.subheader("Chart data")
        st.dataframe(
            combined_trend.rename(
                columns={
                    "snapshot_date": "Snapshot date",
                    "series": "Artist or release",
                    "series_type": "Type",
                    "listen_count": "Listens",
                }
            ),
            width="stretch",
            hide_index=True,
        )