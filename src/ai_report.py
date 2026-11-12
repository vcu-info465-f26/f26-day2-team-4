import os

import pandas as pd
from groq import Groq


def _format_selected_names(music_data):
    artist_names = []
    album_names = []

    if "artist_name" in music_data.columns:
        artist_names = sorted({name for name in music_data["artist_name"].dropna().astype(str) if name})
    if "release_name" in music_data.columns:
        album_names = sorted({name for name in music_data["release_name"].dropna().astype(str) if name})

    selected_artists = ", ".join(artist_names) if artist_names else "no artist selected"
    selected_albums = ", ".join(album_names) if album_names else "no album selected"
    return selected_artists, selected_albums


def make_report(music_data):
    if not isinstance(music_data, pd.DataFrame):
        raise TypeError(
            f"make_report expected a pandas DataFrame, got {type(music_data).__name__}."
        )

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")

    selected_artists, selected_albums = _format_selected_names(music_data)
    user_prompt = (
        f"Selected artist(s): {selected_artists}\n"
        f"Selected album(s): {selected_albums}\n\n"
        "Identify the artist with the highest listencount and the album with the highest listen count. "
        "Return the artist name, artist count, album name, and album count.\n\n"
        f"Data:\n{music_data.to_string(index=False)}"
    )

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a data analyst. Answer the question using the selected filter. "
                    "Report the artist with the highest listen_count and the album with the highest listen_count, "
                    "including each name, its count, and the snapshot_date shown in the data. "
                    "Do not infer listen-count changes between snapshots. "
                    "If the dashboard does not cover the requested information, say 'I don't have that.'"
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        reasoning_effort="low",
    )

    report = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    return report, usage

def ask_question(music_data, messages):
    client=Groq(
    api_key=os.environ.get("GROQ_API_KEY")
    )

    response=client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
        {"role":"system",
         "content":"Answer using only the artist and album data. If it is not in the data say so.\n"
                    +music_data.to_string(index=False)}
        ]+messages, 
        reasoning_effort="low"
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    sample_data = pd.DataFrame(
        {
            "snapshot_date": ["2026-10-27", "2026-10-28"],
            "listen_count": [120, 150],
            "artist_name": ["Artist A", "Artist B"],
            "release_name": ["Album A", "Album B"],
        }
    )
    print(make_report(sample_data))