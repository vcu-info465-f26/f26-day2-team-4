import json
import pathlib
import sqlite3

DATA_DIR = pathlib.Path("data")

conn = sqlite3.connect("project.db")

# Start fresh each time so rows do not duplicate.
conn.execute("DROP TABLE IF EXISTS release_artists")
conn.execute("DROP TABLE IF EXISTS release_stats")
conn.execute("DROP TABLE IF EXISTS artist_stats")

conn.execute("""
CREATE TABLE artist_stats (
    snapshot_date TEXT,
    artist_mbid TEXT,
    artist_name TEXT,
    listen_count INTEGER,
    PRIMARY KEY (snapshot_date, artist_mbid)
)
""")

conn.execute("""
CREATE TABLE release_stats (
    snapshot_date TEXT,
    release_mbid TEXT,
    release_name TEXT,
    artist_name TEXT,
    listen_count INTEGER,
    PRIMARY KEY (snapshot_date, release_mbid)
)
""")

conn.execute("""
CREATE TABLE release_artists (
    snapshot_date TEXT,
    release_mbid TEXT,
    artist_mbid TEXT,
    PRIMARY KEY (snapshot_date, release_mbid, artist_mbid)
)
""")

# Load every artist snapshot in data/.
for path in sorted(DATA_DIR.glob("Artists_*.json")):
    snapshot_date = path.stem.split("_")[-1]

    with open(path) as file:
        artists = json.load(file)

    for artist in artists:
        artist_mbid = artist.get("artist_mbid")

        if artist_mbid:
            conn.execute(
                "INSERT INTO artist_stats VALUES (?, ?, ?, ?)",
                (
                    snapshot_date,
                    artist_mbid,
                    artist.get("artist_name"),
                    artist.get("listen_count"),
                ),
            )

# Load every album snapshot in data/.
for path in sorted(DATA_DIR.glob("Albums_*.json")):
    snapshot_date = path.stem.split("_")[-1]

    with open(path) as file:
        albums = json.load(file)

    for album in albums:
        release_mbid = album.get("release_mbid")

        if release_mbid:
            conn.execute(
                "INSERT INTO release_stats VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot_date,
                    release_mbid,
                    album.get("release_name"),
                    album.get("artist_name"),
                    album.get("listen_count"),
                ),
            )

            for artist_mbid in album.get("artist_mbids", []):
                conn.execute(
                    "INSERT INTO release_artists VALUES (?, ?, ?)",
                    (snapshot_date, release_mbid, artist_mbid),
                )

conn.commit()

artist_count = conn.execute(
    "SELECT COUNT(*) FROM artist_stats"
).fetchone()[0]

release_count = conn.execute(
    "SELECT COUNT(*) FROM release_stats"
).fetchone()[0]

relationship_count = conn.execute(
    "SELECT COUNT(*) FROM release_artists"
).fetchone()[0]

conn.close()

print("Rebuilt project.db")
print(f"artist_stats rows: {artist_count}")
print(f"release_stats rows: {release_count}")
print(f"release_artists rows: {relationship_count}")