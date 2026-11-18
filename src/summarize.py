
import os
import sqlite3
from pathlib import Path
from groq import Groq
from build_db import build


DB_PATH = "project.db"
SUMMARY_PATH = Path("data/summary.md")


def get_music_stats():
    conn = sqlite3.connect(DB_PATH)

    snapshot_date = conn.execute("""
        SELECT MAX(snapshot_date)
        FROM (
            SELECT snapshot_date FROM artist_stats
            INTERSECT
            SELECT snapshot_date FROM release_stats
        )
    """).fetchone()[0]

    if snapshot_date is None:
        conn.close()
        raise ValueError("No matching snapshots found.")

    artists = conn.execute("""
        SELECT artist_name, listen_count
        FROM artist_stats
        WHERE snapshot_date = ?
        AND listen_count IS NOT NULL
        ORDER BY listen_count DESC
        LIMIT 5
    """, (snapshot_date,)).fetchall()

    albums = conn.execute("""
        SELECT release_name, artist_name, listen_count
        FROM release_stats
        WHERE snapshot_date = ?
        AND listen_count IS NOT NULL
        ORDER BY listen_count DESC
        LIMIT 5
    """, (snapshot_date,)).fetchall()

    conn.close()

    artist_stats = "\n".join(
        f"- {name}: {count} listens"
        for name, count in artists
    )

    album_stats = "\n".join(
        f"- {album} by {artist}: {count} listens"
        for album, artist, count in albums
    )

    music_data = (
        f"Snapshot Date: {snapshot_date}\n\n"
        f"Top 5 Artists:\n{artist_stats}\n\n"
        f"Top 5 Albums:\n{album_stats}"
    )

    return music_data


def make_report(music_data):
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY")
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a music listening analyst. "
                    "Write a clear and concise summary of "
                    "the provided ListenBrainz music statistics. "
                    "Use only 2 to 3 short sentences and no more "
                    "than 60 words. "
                    "Identify the most listened to artist and album, "
                    "including their listen counts. "
                    "Briefly mention any noticeable difference "
                    "between the top artist and album if relevant. "
                    "The counts are cumulative as of the snapshot date. "
                    "Only use the provided data. "
                    "Do not make up statistics or information. "
                    "Avoid unnecessary details, headings, and bullet points. "
                )
            },
            {
                "role": "user",
                "content": music_data
            }
        ],
        reasoning_effort="low"
    )

    report = response.choices[0].message.content

    return report


def save_summary(music_data, report):
    summary = (
        "## Music Listening Summary\n\n"
        f"{report}\n"
    )

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    SUMMARY_PATH.write_text(
        summary,
        encoding="utf-8"
    )

    print("Summary saved to data/summary.md")


if __name__ == "__main__":
    build()
    music_data = get_music_stats()
    report = make_report(music_data)
    save_summary(report)
