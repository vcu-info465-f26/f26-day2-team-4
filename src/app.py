import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from ai_report import make_report

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


def get_snapshot_dates(dataframes):
    dates = pd.concat(
        [frame["snapshot_date"] for frame in dataframes if not frame.empty],
        ignore_index=True,
    )
    return sorted(dates.dt.date.unique())


def filter_by_date(frame, selected_dates):
    return frame[frame["snapshot_date"].dt.date.isin(selected_dates)].copy()


def build_label_map(frame, key_field, label_format):
    options = frame.drop_duplicates(key_field).sort_values("listen_count", ascending=False)
    return {label_format(row): getattr(row, key_field) for row in options.itertuples()}


def build_report_heading(selected_dates, all_dates):
    if not selected_dates:
        return "Most listened to artist and album"

    ordered_dates = sorted(selected_dates)
    if len(ordered_dates) == len(all_dates) and all_dates:
        return "Overall most listened to artist and album"

    if len(ordered_dates) == 1:
        return f"Most listened to artist and album for {ordered_dates[0].strftime('%b %d, %Y')}"

    first_date = ordered_dates[0]
    last_date = ordered_dates[-1]
    return (
        "Most listened to artist and album for "
        f"{first_date.strftime('%b %d, %Y')} to {last_date.strftime('%b %d, %Y')}"
    )


def compact_chart(fig):
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            itemwidth=30,
        ),
    )
    return fig


st.title("Listen Count Dashboard")

summary_path = Path(__file__).resolve().parents[1] / "data" / "summary.md"

if summary_path.is_file():
    summary = summary_path.read_text(encoding="utf-8")
    st.markdown(summary)
else:
    st.info("The AI music summary will appear after the next refresh.")

st.divider()


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

available_dates = get_snapshot_dates((artist_data, release_data))

st.sidebar.header("Filters")
selected_dates = st.sidebar.multiselect(
    "Snapshot dates",
    options=available_dates,
    default=available_dates,
    format_func=lambda date: date.strftime("%b %d, %Y"),
)
artists = filter_by_date(artist_data, selected_dates)
releases = filter_by_date(release_data, selected_dates)

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
    "Albums",
    options=list(release_labels),
    default=list(release_labels)[:8],
)
artist_ids = [artist_labels[label] for label in selected_artists]
release_ids = [release_labels[label] for label in selected_releases]

report_df = pd.DataFrame()
if artist_ids or release_ids:
    report_frames = []
    if artist_ids:
        report_frames.append(artists[artists["artist_mbid"].isin(artist_ids)].copy())
    if release_ids:
        report_frames.append(releases[releases["release_mbid"].isin(release_ids)].copy())
    if report_frames:
        report_df = pd.concat(report_frames, ignore_index=True)

if st.button("Generate AI Report"):
    if report_df.empty:
        st.warning("Select an artist or album before generating the report.")
    else:
        music_data = report_df.copy()

        artist_summary = pd.DataFrame()
        album_summary = pd.DataFrame()

        if "artist_name" in music_data.columns:
            artist_summary = (
                music_data.groupby("artist_name", as_index=False)["listen_count"]
                .sum()
                .sort_values("listen_count", ascending=False)
                .head(1)
            )

        if "release_name" in music_data.columns:
            album_summary = (
                music_data.groupby("release_name", as_index=False)["listen_count"]
                .sum()
                .sort_values("listen_count", ascending=False)
                .head(1)
            )

        summary_rows = []
        if not artist_summary.empty:
            top_artist = artist_summary.iloc[0]
            summary_rows.append({
                "artist_name": top_artist["artist_name"],
                "release_name": None,
                "listen_count": int(top_artist["listen_count"]),
            })
        if not album_summary.empty:
            top_album = album_summary.iloc[0]
            summary_rows.append({
                "artist_name": None,
                "release_name": top_album["release_name"],
                "listen_count": int(top_album["listen_count"]),
            })

        music_data = pd.DataFrame(summary_rows, columns=["artist_name", "release_name", "listen_count"])

        st.subheader(build_report_heading(selected_dates, available_dates))
        report, usage = make_report(music_data)
        st.write(report)
        if usage is not None:
            st.write(usage.total_tokens)

album_tab, artist_tab, both_tab = st.tabs(["Albums", "Artists", "Both"])

with album_tab:
    release_trend = releases[releases["release_mbid"].isin(release_ids)].copy()
    if release_trend.empty:
        st.subheader("Album listens over time")
        st.info("Select one or more albums to show this chart.")
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
                "snapshot_date": "Date",
                "listen_count": "Listens",
                "series": "Release",
            },
        )
        fig = compact_chart(fig)
        st.subheader("Album listens over time")
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Chart data")
        st.dataframe(
            release_trend[
                ["snapshot_date", "release_name", "artist_name", "listen_count", "release_mbid"]
            ].rename(
                columns={
                    "snapshot_date": "Date",
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
                "snapshot_date": "Date",
                "listen_count": "Listens",
                "artist_name": "Artist",
            },
        )
        fig = compact_chart(fig)
        st.subheader("Artist listens over time")
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Chart data")
        st.dataframe(
            artist_trend[
                ["snapshot_date", "artist_name", "listen_count", "artist_mbid"]
            ].rename(
                columns={
                    "snapshot_date": "Date",
                    "artist_name": "Artist",
                    "listen_count": "Listens",
                    "artist_mbid": "Artist MBID",
                }
            ),
            width="stretch",
            hide_index=True,
        )

with both_tab:
    st.subheader("Artist and Album listens over time")
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
        release_series["series"] = "Album: " + release_series["release_name"] + " - " + release_series["artist_name"]
        release_series["series_type"] = "Album"
        combined_series.append(
            release_series[["snapshot_date", "series", "series_type", "listen_count"]]
        )

    if not combined_series:
        st.info("Select artists or albums to show the combined chart.")
        filtered = pd.DataFrame()
    else:
        combined_trend = pd.concat(combined_series, ignore_index=True)
        filtered = combined_trend.copy()
        fig = px.line(
            combined_trend,
            x="snapshot_date",
            y="listen_count",
            color="series",
            line_dash="series_type",
            markers=True,
            labels={
                "snapshot_date": "Date",
                "listen_count": "Listens",
                "series": "Artist or Album",
                "series_type": "Type",
            },
        )
        fig = compact_chart(fig)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Chart data")
        st.dataframe(
            combined_trend.rename(
                columns={
                    "snapshot_date": "Date",
                    "series": "Artist or Album",
                    "series_type": "Type",
                    "listen_count": "Listens",
                }
            ),
            width="stretch",
            hide_index=True,
        )