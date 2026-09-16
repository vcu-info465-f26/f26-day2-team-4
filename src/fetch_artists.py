import requests


def get_top_artists():
    response = requests.get(
        "https://api.listenbrainz.org/1/stats/sitewide/artists",
        params={"range": "week", "count": 30}
    )

    data = response.json()

    print(data)
    print(data.keys())
    print(data["payload"].keys())

    return data["payload"]["artists"]


artists = get_top_artists()
print(artists)
