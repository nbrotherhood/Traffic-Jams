import streamlit as st
import pandas as pd
import plotly.express as px
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import datetime

# ---------- CONFIGURATION ----------
CLIENT_ID = "ccd5da2397674bcaa675148a646996c3"
REDIRECT_URI = "https://traffic-jams-spotify-stats.streamlit.app/"
SCOPE = "user-top-read user-read-private user-read-email"
MAX_RESULTS = 50

# ---------- SESSION STATE ----------
if "token_info" not in st.session_state:
    st.session_state.token_info = None
if "sp" not in st.session_state:
    st.session_state.sp = None

# ---------- AUTHENTICATION ----------
def authenticate():
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,
        cache_path=".cache",
        show_dialog=True
    )
    code = st.experimental_get_query_params().get("code")

    if code:
        token_info = sp_oauth.get_access_token(code[0], as_dict=True)
        st.session_state.token_info = token_info
        st.session_state.sp = spotipy.Spotify(auth=token_info["access_token"])
    elif not st.session_state.token_info:
        auth_url = sp_oauth.get_authorize_url()
        st.write("### Please login to Spotify:")
        st.markdown(f"[Click here to login]({auth_url})")
        st.stop()

# ---------- FETCH USER DATA ----------
def get_user_top_items(item_type, time_range="medium_term", limit=MAX_RESULTS):
    if st.session_state.sp:
        return st.session_state.sp.current_user_top_items(type=item_type, time_range=time_range, limit=limit)
    return None

def convert_ms_to_minutes(ms):
    seconds = ms // 1000
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02}"

# ---------- APP START ----------
st.set_page_config(page_title="Spotify Stats App", layout="wide")
st.title("🎵 Your Spotify Listening Insights")

# Authenticate
authenticate()
sp = st.session_state.sp
user = sp.current_user()
st.success(f"Logged in as **{user['display_name']}**")

# ---------- TIME RANGE SELECT ----------
time_ranges = {
    "Last 4 Weeks": "short_term",
    "Last 6 Months": "medium_term",
    "All Time": "long_term"
}
selected_range = st.selectbox("Select Time Range:", list(time_ranges.keys()))
range_key = time_ranges[selected_range]

# ---------- TOP ARTISTS ----------
st.subheader("🎨 Top Artists")
top_artists_data = get_user_top_items("artists", time_range=range_key)
if top_artists_data:
    artist_items = top_artists_data["items"]
    artist_df = pd.DataFrame([{
        "Rank": idx + 1,
        "Name": artist["name"],
        "Genres": ", ".join(artist["genres"]),
        "Popularity": artist["popularity"],
        "Followers": artist["followers"]["total"]
    } for idx, artist in enumerate(artist_items)])
    
    st.dataframe(artist_df, use_container_width=True, hide_index=True)

    # Chart
    fig = px.bar(
        artist_df.head(10),
        x="Name", y="Popularity",
        title="Top 10 Artists by Popularity",
        labels={"Popularity": "Popularity", "Name": "Artist"},
        color="Popularity",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- TOP TRACKS ----------
st.subheader("🎶 Top Tracks")
top_tracks_data = get_user_top_items("tracks", time_range=range_key)
if top_tracks_data:
    track_items = top_tracks_data["items"]
    track_df = pd.DataFrame([{
        "Rank": idx + 1,
        "Track": track["name"],
        "Artist": track["artists"][0]["name"],
        "Album": track["album"]["name"],
        "Duration": convert_ms_to_minutes(track["duration_ms"]),
        "Popularity": track["popularity"]
    } for idx, track in enumerate(track_items)])
    
    st.dataframe(track_df, use_container_width=True, hide_index=True)

    # Chart
    fig = px.bar(
        track_df.head(10),
        x="Track", y="Popularity",
        title="Top 10 Tracks by Popularity",
        labels={"Popularity": "Popularity", "Track": "Track"},
        color="Popularity",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- EXPORT BUTTON ----------
with st.expander("⬇ Export Data"):
    st.download_button("Download Artists CSV", artist_df.to_csv(index=False), "top_artists.csv", "text/csv")
    st.download_button("Download Tracks CSV", track_df.to_csv(index=False), "top_tracks.csv", "text/csv")
