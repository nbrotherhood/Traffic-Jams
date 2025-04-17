import streamlit as st
import pandas as pd
import spotipy
import plotly
from spotipy.oauth2 import SpotifyImplicitGrant
from datetime import datetime
from collections import Counter
import base64
import urllib.parse
import uuid
import requests
import json

st.set_page_config(page_title="Your Spotify Stats")

CLIENT_ID = "ccd5da2397674bcaa675148a646996c3"
REDIRECT_URI = "http://127.0.0.1:3000"
SCOPE = 'user-top-read'

if 'token' not in st.session_state:
    st.session_state.token = None
if 'token_verified' not in st.session_state:
    st.session_state.token_verified = False
if 'state' not in st.session_state:
    st.session_state.state = str(uuid.uuid4())


def get_auth_url():
    auth_params = {
        'client_id': CLIENT_ID,
        'response_type': 'token',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
        'state': st.session_state.state,
        'show_dialog': 'true'
    }

    base_url = "https://accounts.spotify.com/authorize"
    auth_url = f"{base_url}?{urllib.parse.urlencode(auth_params)}"
    return auth_url


def parse_url_fragment():
    try:
        fragment = st.query_params.get('fragment', None)
        if fragment and len(fragment) > 0:
            params = dict(param.split('=') for param in fragment[0].split('&'))
            if 'access_token' in params:
                return params['access_token']
    except:
        pass
    return None


def verify_token(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    return response.status_code == 200


def get_spotify_client(token):
    return spotipy.Spotify(auth=token)


token_from_url = parse_url_fragment()
if token_from_url:
    st.session_state.token = token_from_url

if st.session_state.token and not st.session_state.token_verified:
    if verify_token(st.session_state.token):
        st.session_state.token_verified = True
    else:
        st.session_state.token = None
        st.session_state.token_verified = False

sp = None
if st.session_state.token_verified:
    sp = get_spotify_client(st.session_state.token)


def get_top_items(item_type, limit, time_range):
    if not sp:
        return []

    try:
        if item_type == 'artists':
            return sp.current_user_top_artists(limit=limit, time_range=time_range)['items']
        elif item_type == 'tracks':
            return sp.current_user_top_tracks(limit=limit, time_range=time_range)['items']
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
    return []


def format_duration_ms(ms):
    seconds = (ms // 1000) % 60
    minutes = (ms // (1000 * 60)) % 60
    return f"{minutes}m {seconds}s"


def get_artist_info(artist_id):
    if not sp:
        return {}

    try:
        artist = sp.artist(artist_id)
        return {
            'Name': artist['name'],
            'Followers': artist['followers']['total'],
            'Popularity': artist['popularity'],
            'Genres': ", ".join(artist['genres'])
        }
    except Exception as e:
        st.error(f"Error fetching artist info: {str(e)}")
        return {'Name': 'Unknown', 'Followers': 0, 'Popularity': 0, 'Genres': ''}


def estimate_listening_time(tracks):
    artist_times = {}
    song_times = {}
    for track in tracks:
        duration = track['duration_ms']
        song = track['name']
        artist = track['artists'][0]['name']
        artist_times[artist] = artist_times.get(artist, 0) + duration
        song_times[song] = song_times.get(song, 0) + duration
    return artist_times, song_times


if not st.session_state.token_verified:
    st.title("Spotify Listening Stats")
    st.write("Connect your Spotify account to see your listening statistics")

    auth_url = get_auth_url()
    st.markdown(f"[Click here to authorize with Spotify]({auth_url})")

    st.info(
        "After authorizing, you'll be redirected to a URL containing the access token. Copy the entire URL from your browser's address bar and paste it here:")
    redirect_url = st.text_input("Enter the URL after authorization:")

    if redirect_url:
        try:
            if '#access_token=' in redirect_url:
                fragment_start = redirect_url.find('#access_token=')
                fragment = redirect_url[fragment_start + 1:]
                params = dict(param.split('=') for param in fragment.split('&'))
                if 'access_token' in params:
                    token = params['access_token']
                    if verify_token(token):
                        st.session_state.token = token
                        st.session_state.token_verified = True
                        st.rerun()
                    else:
                        st.error("Invalid token. Please try authorizing again.")
            else:
                st.warning(
                    "The URL doesn't contain an access token. Make sure you're copying the entire URL after authorization.")
        except Exception as e:
            st.error(f"Error processing the URL: {str(e)}")
            st.info("Try copying just the part after '#access_token=' from the URL.")
else:
    st.sidebar.title("Spotify Insights")
    time_range_display = st.sidebar.selectbox("Select Time Range", ["Last Month", "Last 6 Months", "Last Year"])
    time_range_api = {
        "Last Month": "short_term",
        "Last 6 Months": "medium_term",
        "Last Year": "long_term"
    }[time_range_display]

    limit = st.sidebar.slider("Select number of results (1-50)", 1, 50, 10)

    st.sidebar.header("Filters")
    popularity_range = st.sidebar.select_slider(
        "Filter Artists by Popularity (0-100)",
        options=list(range(0, 101)),
        value=(0, 100)
    )

    pie_threshold = st.sidebar.slider(
        "Minimum % for Pie Chart Inclusion (0%-10%)",
        min_value=0.00,
        max_value=10.00,
        value=1.00,
        step=0.01,
        format="%.2f%%",
    )

    st.sidebar.header("Show/Hide Sections")
    show_artists = st.sidebar.checkbox("Show Top Artists", value=True)
    show_songs = st.sidebar.checkbox("Show Top Songs", value=True)
    show_artist_pie = st.sidebar.checkbox("Show Artist Concentration", value=True)
    show_genre_pie = st.sidebar.checkbox("Show Genre Distribution", value=True)
    show_popularity = st.sidebar.checkbox("Show Artist Popularity Chart", value=True)

    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.token_verified = False
        st.rerun()

    st.title("Your Spotify Listening Stats")

    top_artists = get_top_items('artists', limit, time_range_api)
    top_tracks = get_top_items('tracks', limit, time_range_api)

    artist_data = []
    for artist in top_artists:
        info = get_artist_info(artist['id'])
        if popularity_range[0] <= info['Popularity'] <= popularity_range[1]:
            artist_data.append([
                info['Name'],
                info['Followers'],
                info['Popularity'],
                info['Genres']
            ])

    artist_df = pd.DataFrame(artist_data, columns=['Artist', 'Followers', 'Popularity', 'Genres'])

    if len(artist_df) > 0 and show_artists:
        artist_df.index = range(1, len(artist_df) + 1)
        artist_df.reset_index(inplace=True)
        artist_df.rename(columns={'index': 'Rank'}, inplace=True)

        st.header(f"Top {len(artist_df)} Artists ({time_range_display})")
        st.dataframe(artist_df, use_container_width=True, hide_index=True)

        artists_export_success = st.empty()

        csv = artist_df.to_csv(index=False)
        if st.download_button(
                label="Export Artists to CSV",
                data=csv,
                file_name=f"spotify_top_artists_{time_range_api}.csv",
                mime="text/csv",
                key="artists_export"
        ):
            artists_export_success.success("Success: Data exported to CSV!")
    elif show_artists:
        st.header(f"Top Artists ({time_range_display})")
        st.warning("No artists found within the selected popularity range.")

    track_data = []
    for track in top_tracks:
        track_data.append([
            track['name'],
            track['artists'][0]['name'],
            format_duration_ms(track['duration_ms'])
        ])

    track_df = pd.DataFrame(track_data, columns=['Song', 'Artist', 'Duration'])
    track_df.index = range(1, len(track_df) + 1)
    track_df.reset_index(inplace=True)
    track_df.rename(columns={'index': 'Rank'}, inplace=True)

    if show_songs:
        st.header(f"Top {limit} Songs ({time_range_display})")
        st.dataframe(track_df, use_container_width=True, hide_index=True)

        songs_export_success = st.empty()

        csv = track_df.to_csv(index=False)
        if st.download_button(
                label="Export Songs to CSV",
                data=csv,
                file_name=f"spotify_top_songs_{time_range_api}.csv",
                mime="text/csv",
                key="songs_export"
        ):
            songs_export_success.success("Success: Data exported to CSV!")

    if show_popularity and len(artist_df) > 0:
        st.header("Artist Popularity Comparison")
        popularity_df = artist_df[['Rank', 'Artist', 'Popularity']].copy()

        popularity_df = popularity_df.sort_values('Rank')

        fig_popularity = {
            'data': [{
                'type': 'bar',
                'x': popularity_df['Rank'].tolist(),
                'y': popularity_df['Popularity'].tolist(),
                'marker': {
                    'color': 'rgb(30, 215, 96)',
                    'opacity': 0.8,
                },
                'text': popularity_df['Artist'].tolist(),
                'hoverinfo': 'text+y',
                'name': 'Popularity',
            }],
            'layout': {
                'title': f'Artist Popularity vs Rank (Filtered: {popularity_range[0]}-{popularity_range[1]})',
                'xaxis': {'title': 'Rank', 'tickmode': 'linear'},
                'yaxis': {'title': 'Popularity (0-100)', 'range': [0, 100]},
            }
        }
        st.plotly_chart(fig_popularity, use_container_width=True)

    elif show_popularity:
        st.header("Artist Popularity Comparison")
        st.warning("No artists found within the selected popularity range.")

    artist_times, song_times = estimate_listening_time(top_tracks)

    if show_artist_pie:
        st.header("Artist Concentration in Your Top Songs")
        artist_counts = Counter([track['artists'][0]['name'] for track in top_tracks])

        total_count = sum(artist_counts.values())

        if total_count > 0:
            threshold_count = (pie_threshold / 100) * total_count

            above_threshold = {artist: count for artist, count in artist_counts.items()
                               if count >= threshold_count}
            below_threshold = {artist: count for artist, count in artist_counts.items()
                               if count < threshold_count}

            artist_pie_data = above_threshold.copy()
            if below_threshold:
                artist_pie_data["Other Artists"] = sum(below_threshold.values())

            artist_concentration_df = pd.DataFrame({
                'Artist': list(artist_pie_data.keys()),
                'Count': list(artist_pie_data.values())
            }).sort_values(by='Count', ascending=False)

            fig_artist_pie = {
                'data': [{'type': 'pie',
                          'labels': artist_concentration_df['Artist'].tolist(),
                          'values': artist_concentration_df['Count'].tolist(),
                          'hole': 0.4,
                          'hoverinfo': 'label+percent+value'}],
                'layout': {'title': 'Proportion of Top Songs by Artist'}
            }
            st.plotly_chart(fig_artist_pie, use_container_width=True)

            st.caption(f"Artists representing less than {pie_threshold}% of your tracks are grouped as 'Other Artists'")
        else:
            st.warning("No artist data available for pie chart.")

    if show_genre_pie:
        st.header("Genre Concentration")
        all_genres = []

        for artist in top_artists:
            all_genres.extend(artist['genres'])

        genre_counts = Counter(all_genres)

        if '' in genre_counts:
            del genre_counts['']
        if ' ' in genre_counts:
            del genre_counts[' ']

        non_empty_genres = {genre: count for genre, count in genre_counts.items() if genre.strip()}

        total_count = sum(non_empty_genres.values())

        if total_count > 0:
            threshold_count = (pie_threshold / 100) * total_count

            above_threshold = {genre: count for genre, count in non_empty_genres.items()
                               if count >= threshold_count}
            below_threshold = {genre: count for genre, count in non_empty_genres.items()
                               if count < threshold_count}

            genre_pie_data = above_threshold.copy()
            if below_threshold:
                genre_pie_data["Other Genres"] = sum(below_threshold.values())

            fig_genre_pie = {
                'data': [{'type': 'pie',
                          'labels': list(genre_pie_data.keys()),
                          'values': list(genre_pie_data.values()),
                          'hole': 0.4,
                          'hoverinfo': 'label+percent+value'}],
                'layout': {'title': 'Distribution of Your Top Genres'}
            }
            st.plotly_chart(fig_genre_pie, use_container_width=True)

            st.caption(
                f"Genres representing less than {pie_threshold}% of your total genre occurrences are grouped as 'Other Genres'")
        else:
            st.warning("No genre data available for pie chart.")

    if top_artists and top_tracks:
        with st.expander("**Export All Data**", expanded=True):
            all_data = {
                "artists": pd.DataFrame([{
                    "rank": i + 1,
                    "name": artist["name"],
                    "popularity": artist["popularity"],
                    "followers": artist["followers"]["total"],
                    "genres": ", ".join(artist["genres"]),
                    "spotify_id": artist["id"],
                    "time_range": time_range_api
                } for i, artist in enumerate(top_artists)]),

                "tracks": pd.DataFrame([{
                    "rank": i + 1,
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album": track["album"]["name"],
                    "duration_ms": track["duration_ms"],
                    "popularity": track["popularity"],
                    "spotify_id": track["id"],
                    "time_range": time_range_api
                } for i, track in enumerate(top_tracks)])
            }

            from io import StringIO

            buffer = StringIO()
            buffer.write("# SPOTIFY LISTENING STATS\n\n")
            buffer.write(f"# Time Range: {time_range_display}\n")
            buffer.write(f"# Date Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            buffer.write("# TOP ARTISTS\n")
            all_data["artists"].to_csv(buffer, index=False)
            buffer.write("\n\n# TOP TRACKS\n")
            all_data["tracks"].to_csv(buffer, index=False)

            csv_data = buffer.getvalue()

            all_data_export_success = st.empty()

            if st.download_button(
                    label="Export All Data to CSV",
                    data=csv_data,
                    file_name=f"spotify_listening_data_{time_range_api}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="all_data_export"
            ):
                all_data_export_success.success("Success: Data exported to CSV!")

    with st.expander("**About Time Ranges:**", expanded=True):st.info("""
    **Time Ranges:**
    - **Last Month**: Reflects your short-term listening habits over approximately the last 4 weeks
    - **Last 6 Months**: Reflects your medium-term listening habits over approximately 6 months
    - **Last Year**: Reflects your long-term listening habits over approximately 1 year
    """)
