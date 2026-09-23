import sqlite3
import pandas as pd

DB_PATH = "project.db"

def get_artist_releases():
    conn = sqlite3.connect(DB_PATH)
    results = pd.read_sql_query(
        """
        SELECT
        artist_stats.artist_name,
        artist_stats.listen_count AS artist_listens,
        release_stats.release_name,
        release_stats.listen_count AS release_listens

        FROM artist_stats
        JOIN release_artists
            ON artist_stats.artist_mbid = release_artists.artist_mbid
            AND artist_stats.snapshot_date = release_artists.snapshot_date
        JOIN release_stats
            ON release_artists.release_mbid = release_stats.release_mbid
            AND release_artists.snapshot_date = release_stats.snapshot_date
        """,
        conn,
    )

    conn.close()
    return results

if __name__ == "__main__":
    print(get_artist_releases())