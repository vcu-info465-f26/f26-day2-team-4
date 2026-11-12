We chose the ListenBrainz API, which gathers data about music such as the artists, albums, and the amount of time they were popular. 
Our two endpoints determine the top 30 listened to artists and albums of the week. 
Both of our endpoints fetch "count," which helps to narrow down our answer output list to a certain number of outputs.

## Sprint 2 Dashboard

Public dashboard: https://f26-day2-team-4project-lmbvcmzq4ax9mjaujns7wd.streamlit.app/

To run the dashboard locally, install the packages with `pip install -r requirements.txt`. Then run `python src/build_db.py` to rebuild the database from the committed snapshots. Start the dashboard with `streamlit run src/app.py`.

## Sprint 3: Summary and Chat

The workflow saves dated ListenBrainz snapshots in `data/`. It runs every other day and can also be started manually from GitHub Actions.

The workflow rebuilds `project.db` from the snapshots, then runs `src/summarize.py`. That script uses the latest date shared by the artist and album data to create `data/summary.md` with listening statistics and an AI summary. The dashboard displays that file and its snapshot date. `project.db` is derived from the snapshots and is not committed.

If summary generation fails, the workflow continues to commit the new snapshot, and the existing summary remains in place.

### Required secret names

- GitHub repository secret: `GROQ_API_KEY`
- GitHub organization secret used by the workflow: `REFRESH_TOKEN1`
- Streamlit Community Cloud app secret: `GROQ_API_KEY`
