import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from groq import GroqError
from ai_report import ask_question, make_report

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


@st.cache_data(ttl=86400, show_spinner=False)
def get_artist_image(artist_name):
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f'"{artist_name}" musician',
                "gsrlimit": 1,
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": 250,
                "format": "json",
                "redirects": 1,
            },
            headers={"User-Agent": "ListenCountDashboard/1.0 (music summary)"},
            timeout=8,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        image_url = next(
            (
                page["thumbnail"]["source"]
                for page in pages.values()
                if page.get("thumbnail", {}).get("source")
            ),
            None,
        )
        return image_url, None
    except requests.RequestException as error:
        return None, str(error)


@st.cache_data(ttl=86400, show_spinner=False)
def get_artist_image_by_mbid(artist_mbid):
    headers = {
        "User-Agent": "ListenCountDashboard/1.0 (https://github.com/vcu-info465-f26/f26-day2-team-4)"
    }

    try:
        time.sleep(1.1)
        artist_response = requests.get(
            f"https://musicbrainz.org/ws/2/artist/{artist_mbid}",
            params={"inc": "url-rels", "fmt": "json"},
            headers=headers,
            timeout=8,
        )
        if artist_response.status_code == 404:
            return None, None
        artist_response.raise_for_status()
        wikidata_url = next(
            (
                relation["url"]["resource"]
                for relation in artist_response.json().get("relations", [])
                if relation.get("type") == "wikidata"
                and (relation.get("url") or {}).get("resource")
            ),
            None,
        )
        if not wikidata_url:
            return None, None

        wikidata_id = wikidata_url.rstrip("/").rsplit("/", 1)[-1]
        wikidata_response = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": wikidata_id,
                "props": "claims",
                "format": "json",
            },
            headers=headers,
            timeout=8,
        )
        wikidata_response.raise_for_status()
        entities = wikidata_response.json().get("entities", {})
        image_claims = (
            entities.get(wikidata_id, {}).get("claims", {}).get("P18", [])
        )
        image_name = next(
            (
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value")
                for claim in image_claims
                if claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            ),
            None,
        )
        if not image_name:
            return None, None

        commons_response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": f"File:{image_name}",
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 250,
                "format": "json",
            },
            headers=headers,
            timeout=8,
        )
        commons_response.raise_for_status()
        pages = commons_response.json().get("query", {}).get("pages", {})
        image_url = next(
            (
                image_info["thumburl"]
                for page in pages.values()
                for image_info in page.get("imageinfo", [])
                if image_info.get("thumburl")
            ),
            None,
        )
        return image_url, None
    except requests.RequestException as error:
        return None, str(error)


def get_local_album_cover(release_mbid):
    cover_dir = Path(__file__).resolve().parent / "assets" / "album_covers"
    if not cover_dir.is_dir():
        return None

    local_covers = [
        path
        for path in cover_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and release_mbid.lower().startswith(path.stem.lower())
    ]
    if not local_covers:
        return None

    return str(max(local_covers, key=lambda path: len(path.stem)))


@st.cache_data(ttl=86400, show_spinner=False)
def get_remote_album_cover(release_mbid):
    image_url = (
        f"https://coverartarchive.org/release/{release_mbid}/front-1200"
    )
    try:
        response = requests.head(image_url, allow_redirects=True, timeout=8)
        if response.status_code == 404:
            return None, None
        response.raise_for_status()
        return image_url, None
    except requests.RequestException as error:
        return None, str(error)


def get_album_cover(release_mbid):
    local_cover = get_local_album_cover(release_mbid)
    if local_cover:
        return local_cover, None
    return get_remote_album_cover(release_mbid)


def get_ranked_artist_image(artist_name, artist_mbid):
    image_url, image_error = get_artist_image(artist_name)
    if image_url:
        return image_url, None

    if artist_mbid:
        mbid_image_url, mbid_error = get_artist_image_by_mbid(artist_mbid)
        if mbid_image_url:
            return mbid_image_url, None
        if mbid_error:
            return None, mbid_error

    return None, image_error


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


def previous_week_bounds(today=None):
    today = today or date.today()
    this_week_start = today - timedelta(days=today.weekday())
    return this_week_start - timedelta(days=7), this_week_start - timedelta(days=1)


def latest_snapshot_in_week(frame, week_start, week_end):
    in_week = frame[frame["snapshot_date"].dt.date.between(week_start, week_end)]
    if in_week.empty:
        return in_week.copy()

    latest_date = in_week["snapshot_date"].max()
    return in_week[in_week["snapshot_date"] == latest_date].copy()


def build_report_data(artist_data, release_data):
    summary_rows = []

    if not artist_data.empty:
        top_artist = (
            artist_data.groupby(
                ["snapshot_date", "artist_mbid", "artist_name"], as_index=False
            )["listen_count"]
            .sum()
            .sort_values("listen_count", ascending=False)
            .iloc[0]
        )
        summary_rows.append({
            "snapshot_date": top_artist["snapshot_date"].date().isoformat(),
            "artist_name": top_artist["artist_name"],
            "release_name": None,
            "listen_count": int(top_artist["listen_count"]),
        })

    if not release_data.empty:
        top_album = (
            release_data.groupby(
                ["snapshot_date", "release_mbid", "release_name", "artist_name"],
                as_index=False,
            )["listen_count"]
            .sum()
            .sort_values("listen_count", ascending=False)
            .iloc[0]
        )
        summary_rows.append({
            "snapshot_date": top_album["snapshot_date"].date().isoformat(),
            "artist_name": None,
            "release_name": top_album["release_name"],
            "listen_count": int(top_album["listen_count"]),
        })

    return pd.DataFrame(
        summary_rows,
        columns=["snapshot_date", "artist_name", "release_name", "listen_count"],
    )


def compact_chart(fig):
    fig.update_layout(
        height=450,
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


st.title("🎵 Listen Count Dashboard 🎵")

st.caption("This dashboard uses data from the ListenBrainz API "
"to track music trends, including popular artists, albums,"
" and the duration of their popularity over time.")

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

artist_dates = set(artist_data["snapshot_date"].dt.date)
release_dates = set(release_data["snapshot_date"].dt.date)
shared_dates = artist_dates & release_dates
summary_dates = shared_dates or artist_dates or release_dates
summary_snapshot_date = max(summary_dates)
summary_artists = (
    artist_data[artist_data["snapshot_date"].dt.date == summary_snapshot_date]
    .sort_values("listen_count", ascending=False)
    .head(5)
)
summary_releases = (
    release_data[release_data["snapshot_date"].dt.date == summary_snapshot_date]
    .sort_values("listen_count", ascending=False)
    .head(5)
)

st.subheader("Artist and Album Rankings")
st.caption(f"Snapshot date: {summary_snapshot_date.strftime('%b %d, %Y')}")
artist_column, album_column = st.columns(2)

with artist_column:
    st.markdown("#### Artists")
    for rank, artist in enumerate(summary_artists.itertuples(), start=1):
        image_url, image_error = get_ranked_artist_image(
            artist.artist_name, artist.artist_mbid
        )
        image_column, details_column = st.columns([1, 3])
        with image_column:
            if image_url:
                st.image(image_url, width=90)
            else:
                st.write("🎤")
        with details_column:
            st.markdown(f"**{rank}. {artist.artist_name}**")
            st.caption(f"{artist.listen_count:,} listens")
        if image_error:
            st.warning(f"Could not load an image for {artist.artist_name}: {image_error}")

with album_column:
    st.markdown("#### Albums")
    for rank, album in enumerate(summary_releases.itertuples(), start=1):
        image_url, image_error = get_album_cover(album.release_mbid)
        image_column, details_column = st.columns([1, 3])
        with image_column:
            if image_url:
                st.image(image_url, width=90)
            else:
                st.write("💿")
        with details_column:
            st.markdown(f"**{rank}. {album.release_name}**")
            st.caption(f"{album.artist_name} · {album.listen_count:,} listens")
        if image_error:
            st.warning(f"Could not load cover art for {album.release_name}: {image_error}")

st.divider()

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
    latest_artists = artists
    latest_releases = releases
else:
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

selected_artist_data = artists[artists["artist_mbid"].isin(artist_ids)].copy()
selected_release_data = releases[releases["release_mbid"].isin(release_ids)].copy()
report_frames = [
    frame
    for frame in (selected_artist_data, selected_release_data)
    if not frame.empty
]
report_df = pd.concat(report_frames, ignore_index=True) if report_frames else pd.DataFrame()

album_tab, artist_tab, both_tab = st.tabs(["Albums", "Artists", "Both"])

with album_tab:
    release_trend = releases[releases["release_mbid"].isin(release_ids)].copy()
    if release_trend.empty:
        st.subheader("💿 Album listens over time")
        st.info("Select one or more albums to show this chart.")
    else:
        release_trend["series"] = (
    release_trend["release_name"]
    + " - "
    + release_trend["artist_name"]
    + " ["
    + release_trend["release_mbid"].str[:8]
    + "]"
)
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
        st.subheader("Album Listens Over Time 💿 ")
        st.plotly_chart(fig, width="stretch", height=450)
        st.subheader("🎶 Music Data 🎶")
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
        st.subheader("Artist Listens Over Time 🎤")
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
        st.subheader("Artist Listens Over Time 🎤")
        st.plotly_chart(fig, width="stretch",height=450)
        st.subheader("🎶 Music Data 🎶")
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
    st.subheader("Artist and Album Listens Over Time 🎧 ")
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
        st.plotly_chart(fig, width="stretch")
        st.subheader("🎶 Music Data 🎶")
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

if "messages" not in st.session_state:
    st.session_state.messages = []

question = st.chat_input("Ask a question about the music artists and albums!")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    if report_df.empty:
        st.warning("Select at least one artist or album before asking a question.")
    else:
        try:
            answer = ask_question(report_df.tail(50), st.session_state.messages)
        except GroqError as error:
            st.error(f"Could not get an answer from the AI service: {error}")
        else:
            st.session_state.messages.append({"role": "assistant", "content": answer})

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if st.button("Generate AI Report"):
    st.subheader("AI Listen Tracking Report")
    week_start, week_end = previous_week_bounds()
    weekly_artists = latest_snapshot_in_week(artist_data, week_start, week_end)
    weekly_releases = latest_snapshot_in_week(release_data, week_start, week_end)
    st.caption(
        f"Previous week: {week_start.strftime('%b %d, %Y')} – "
        f"{week_end.strftime('%b %d, %Y')}"
    )
    report_data = build_report_data(weekly_artists, weekly_releases)
    if report_data.empty:
        st.warning("No artist or album snapshots were taken during the previous week.")
    else:
        snapshot_dates = ", ".join(sorted(report_data["snapshot_date"].unique()))
        st.caption(f"Using the latest available snapshot(s): {snapshot_dates}")
        report, usage = make_report(report_data)
        st.write(report)
        if usage is not None:
            st.write(usage.total_tokens)