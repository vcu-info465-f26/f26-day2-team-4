import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "project.db"

st.set_page_config(page_title="Listen Count Dashboard", layout="wide")


@st.cache_data
def load_data(database_path):
    with sqlite3.connect(database_path) as connection:
        artists = pd.read_sql_query(
            "SELECT snapshot_date, artist_mbid, artist_name, listen_count "
            "FROM artist_stats",
            connection,
        )
        releases = pd.read_sql_query(
            "SELECT snapshot_date, release_mbid, release_name, artist_name, listen_count "
            "FROM release_stats",
            connection,
        )

    artists["snapshot_date"] = pd.to_datetime(artists["snapshot_date"])
    releases["snapshot_date"] = pd.to_datetime(releases["snapshot_date"])
    return artists, releases


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

artists = artist_data
releases = release_data

if artists.empty and releases.empty:
    st.info("No snapshots match the selected date range.")
    st.stop()

latest_date = max(
    [frame["snapshot_date"].max() for frame in (artists, releases) if not frame.empty]
)
latest_artists = artists[artists["snapshot_date"] == latest_date]
latest_releases = releases[releases["snapshot_date"] == latest_date]

artist_options = latest_artists.drop_duplicates("artist_mbid").sort_values(
    "listen_count", ascending=False
)
artist_labels = {
    f"{row.artist_name} [{row.artist_mbid[:8]}]": row.artist_mbid
    for row in artist_options.itertuples()
}
release_options = latest_releases.drop_duplicates("release_mbid").sort_values(
    "listen_count", ascending=False
)
release_labels = {
    f"{row.release_name} - {row.artist_name} [{row.release_mbid[:8]}]": row.release_mbid
    for row in release_options.itertuples()
}

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
    st.subheader("Release listens over time")
    release_trend = releases[releases["release_mbid"].isin(release_ids)].copy()
    if release_trend.empty:
        st.info("Select one or more releases to show this chart.")
    else:
        release_trend["series"] = (
            release_trend["release_name"] + " - " + release_trend["artist_name"]
        )
        figure = px.line(
            release_trend,
            x="snapshot_date",
            y="listen_count",
            color="series",
            markers=True,
            hover_data=["release_mbid"],
            labels={"snapshot_date": "Snapshot date", "listen_count": "Listens", "series": "Release"},
        )
        st.plotly_chart(figure, width="stretch")
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
    st.subheader("Artist listens over time")
    artist_trend = artists[artists["artist_mbid"].isin(artist_ids)].copy()
    if artist_trend.empty:
        st.info("Select one or more artists to show this chart.")
    else:
        figure = px.line(
            artist_trend,
            x="snapshot_date",
            y="listen_count",
            color="artist_name",
            markers=True,
            hover_data=["artist_mbid"],
            labels={"snapshot_date": "Snapshot date", "listen_count": "Listens", "artist_name": "Artist"},
        )
        st.plotly_chart(figure, width="stretch")
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
        release_series["series"] = (
            "Release: " + release_series["release_name"] + " - " + release_series["artist_name"]
        )
        release_series["series_type"] = "Release"
        combined_series.append(
            release_series[["snapshot_date", "series", "series_type", "listen_count"]]
        )

    if not combined_series:
        st.info("Select artists or releases to show the combined chart.")
    else:
        combined_trend = pd.concat(combined_series, ignore_index=True)
        figure = px.line(
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
        st.plotly_chart(figure, width="stretch")
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