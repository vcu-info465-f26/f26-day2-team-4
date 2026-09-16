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
            artist = album_info.get('artist_name')
            album = album_info.get('release_name')
            if artist and album:
                albums_data.append({
                    "Artist": artist,
                    "Album": album
                })

    if albums_data:
        return pd.DataFrame(albums_data)
    else:
        return pd.DataFrame(columns=["Artist", "Album"])

top_albums = get_most_listened_albums_today()

top_albums.to_json(DATA_DIR / f"Album_{today}.json", indent=2, orient='records')

def get_top_artists():
    response = requests.get(
        "https://api.listenbrainz.org/1/stats/sitewide/artists",
        params={"range": "week", "count": 30})

    artist_data = response.json()
    return artist_data["payload"]["artists"]


artists = get_top_artists()
with open(DATA_DIR / f"Artists_{today}.json", "w") as f:
        json.dump(artists, f, indent=2, sort_keys=True)


print(f"Saved{today}")