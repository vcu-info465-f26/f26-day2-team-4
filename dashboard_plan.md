# Sprint 2 Dashboard Plan

## Insight 1: Artist listens over time

Question: Which top artists gain or lose weekly listens across our snapshot dates?

Data: `artist_stats` using `snapshot_date`, `artist_name`, and `listen_count`.

Plot: A line chart with snapshot dates on the x-axis and weekly artist listen counts on the y-axis.

Why it is useful: It shows whether an artist’s weekly listen count is going up or down instead of showing only one day.

## Insight 2: Release listens over time

Question: Which releases linked to the top artists gain or lose weekly listens across our snapshot dates?

Data: `release_stats`, joined to `release_artists` by artist MBID and snapshot date.

Plot: A line chart with snapshot dates on the x-axis and weekly release listen counts on the y-axis.

Why it is useful: It shows which albums or releases are changing over time and connects them to artists.

## Filter

The dashboard will have a date-range filter. It will update both charts and the dataframe. If no data matches the selected dates, the dashboard will show an empty result instead of an error.