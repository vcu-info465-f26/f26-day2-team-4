import pandas as pd
import requests
import datetime
import time
import pathlib
import json

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(exist_ok=True)

today = datetime.date.today().strftime("%Y-%m-%d")


def get_most_listened_albums_today():

    current_date = datetime.datetime.now()

    start_of_period = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_period = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    from_timestamp = int(time.mktime(start_of_period.timetuple()))
    to_timestamp = int(time.mktime(end_of_period.timetuple()))

    url = "https://api.listenbrainz.org/1/stats/sitewide/releases"
    params = {
        "from": from_timestamp,
        "to": to_timestamp,
        "count": 30
    }

    response = requests.get(url, params=params, timeout=10)

    response.raise_for_status()

    full_response = response.json()

    albums_data = []
    if full_response and 'payload' in full_response and 'releases' in full_response['payload']:
        for album_info in full_response['payload']['releases']:
            artist_name = album_info.get('artist_name')
            artist_mbid = album_info.get('artist_mbids')
            release_name = album_info.get('release_name')
            release_mbid = album_info.get('release_mbid')
            listen_count = album_info.get('listen_count')
            if artist_name and release_name:
                albums_data.append({
                    "artist_name": artist_name,
                    "artist_mbid": artist_mbid,
                    "release_name": release_name,
                    "release_mbid": release_mbid,
                    "listen_count": listen_count
                })

    if albums_data:
        return pd.DataFrame(albums_data)
    else:
        return pd.DataFrame(columns=["artist_name", "artist_mbid","release_name",
                                     "release_mbid","listen_count"])

top_albums = get_most_listened_albums_today()

top_albums.to_json(DATA_DIR / f"Albums_{today}.json", indent=2, orient='records')

def get_top_artists():
    response = requests.get(
        "https://api.listenbrainz.org/1/stats/sitewide/artists",
        params={"range": "week", "count": 30})

    artist_response = response.json()
    artist_data = []
    if artist_response and 'payload' in artist_response and 'artists' in artist_response['payload']:
            for artist_info in artist_response['payload']['artists']:
                artist_name = artist_info.get('artist_name')
                artist_mbid = artist_info.get('artist_mbid')
                listen_count = artist_info.get('listen_count')
                if artist_name:
                    artist_data.append({
                        "artist_name": artist_name,
                        "artist_mbid": artist_mbid,
                        "listen_count": listen_count
                    })
    if artist_data:
        return pd.DataFrame(artist_data)
    else:
        return pd.DataFrame(columns=["artist_name", "artist_mbid","listen_count"])
   

artists = get_top_artists()
artists.to_json(DATA_DIR / f"Artists_{today}.json", indent=2, orient='records')


print(f"Saved{today}")