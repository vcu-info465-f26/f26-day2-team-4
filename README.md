We chose the ListenBrainz API, which gathers data about music such as the artists, albums, and the amount of time they were popular. 
Our two endpoints determine the top 30 listened to artists and albums of the week. 
Both of our endpoints fetch "count," which helps to narrow down our answer output list to a certain number of outputs.

## Sprint 2 Dashboard

Public dashboard: https://f26-day2-team-4project-lmbvcmzq4ax9mjaujns7wd.streamlit.app/

To run the dashboard locally, install the packages with `pip install -r requirements.txt`. Then run `python src/build_db.py` to rebuild the database from the committed snapshots. Start the dashboard with `streamlit run src/app.py`.
