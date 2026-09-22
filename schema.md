# ListenBrainz Schema Sketch

Our project uses the ListenBrainz sitewide artists and releases endpoints. The data will be separated into three tables so artist statistics, release statistics, and artist-release relationships are stored clearly.

## artist_stats

| Field | Type | Description |
|---|---|---|
| snapshot_date | TEXT | Date the API data was collected |
| artist_mbid | TEXT | MusicBrainz artist ID |
| artist_name | TEXT | Artist's name |
| listen_count | INTEGER | Number of artist listens |

Primary key: `snapshot_date` and `artist_mbid`

## release_stats

| Field | Type | Description |
|---|---|---|
| snapshot_date | TEXT | Date the API data was collected |
| release_mbid | TEXT | MusicBrainz release ID |
| release_name | TEXT | Album or release name |
| artist_name | TEXT | Name shown for the release |
| listen_count | INTEGER | Number of release listens |

Primary key: `snapshot_date` and `release_mbid`

## release_artists

| Field | Type | Description |
|---|---|---|
| snapshot_date | TEXT | Date the API data was collected |
| release_mbid | TEXT | MusicBrainz release ID |
| artist_mbid | TEXT | MusicBrainz artist ID |

Primary key: `snapshot_date`, `release_mbid`, and `artist_mbid`

## How the tables connect

The shared join field is `artist_mbid`. The artists endpoint returns one `artist_mbid`, while the releases endpoint returns an `artist_mbids` list because a release can have more than one artist. Each ID from that list will be stored in `release_artists`.

The tables are joined using:

- `artist_stats.artist_mbid = release_artists.artist_mbid`
- `release_stats.release_mbid = release_artists.release_mbid`
- `snapshot_date` keeps the joined records from the same collection day

The tables are separate because an artist can have multiple releases and a release can have multiple artists. This avoids putting a list of artist IDs into one database field and makes the SQL join easier.