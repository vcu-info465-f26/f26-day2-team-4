import pandas as pd
import requests
import datetime
import time

def get_most_listened_albums_last_5_years():
    
    current_year = datetime.datetime.now().year

    start_of_period = datetime.datetime(current_year - 5, 1, 1, 0, 0, 0)
    end_of_period = datetime.datetime(current_year, 12, 31, 23, 59, 59)

    from_timestamp = int(time.mktime(start_of_period.timetuple()))
    to_timestamp = int(time.mktime(end_of_period.timetuple()))

    url = "https://api.listenbrainz.org/1/stats/sitewide/releases"
    params = {
        "from": from_timestamp,
        "to": to_timestamp,
        "count": 10  
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

top_ten_albums = get_most_listened_albums_last_5_years()
print(top_ten_albums)
