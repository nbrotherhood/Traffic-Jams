import streamlit as st
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
from collections import Counter
from io import StringIO

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(page_title="Your Spotify Stats")

# ======================
# SPOTIFY CONFIG
# ======================
CLIENT_ID = "ccd5da2397674bcaa675148a646996c3"
CLIENT_SECRET = ""  # PKCE does not require a client secret
REDIRECT_URI = "https://traffic-jams-spotify-stats.streamlit.app/"
SCOPE = "user-top-read"

# ======================
# SESSION STATE
# ======================
if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=None,
        show_dialog=True
    )

if "sp" not in st.session_state:
    st.session_state.sp = None

# ======================
# HANDLE OAUTH CALLBACK
# ======================
query_params = st.query_params

if "code" in query_params:
    token_info = st.session_state.auth_manager.get_access_token(
        query_params["code"], as_dict=True
    )
    st.session_state.sp = spotipy.Spotify(
        auth=token_info["access_token"]
    )
    st.query_params.clear()
    st.rerun()

# ======================
# LOGIN SCREEN
# ======================
if not st.session_state.sp:
    st.title("Spotify Listening Stats")
    st.write("Connect your Spotify account to see your listening statistics.")

    auth_url = st.session_state.auth_manager.get_authorize_url()
    st.markdown(f"### [Login with Spotify]({auth_url})")
    st.stop()

# ======================
# SPOTIFY CLIENT
# ======================
sp = st.session_state.sp

# ======================
# HELPER FUNCTIONS
# ======================
def get_top_items(item_type, limit, time_range):
    try:
        if item_type == "artists":
            return sp.current_user_top_artists(
                limit=limit, time_range=time_range
            )["items"]
        elif item_type == "tracks":
            return sp.current_user_top_tracks(
                limit=limit, time_range=time_range
            )["items"]
    except Exception as e:
        st.error(f"Error fetching data: {e}")
    return []

def format_duration_ms(ms):
    seconds = (ms // 1000) % 60
    minutes = (ms // (1000 * 60)) % 60
    return f"{minutes}m {seconds}s"

def get_artist_info(artist_id):
    artist = sp.artist(artist_id)
    return {
        "Name": artist["name"],
        "Followers": artist["followers"]["total"],
        "Popularity": artist["popularity"],
        "Genres": ", ".join(artist["genres"])
    }

# ======================
# SIDEBAR
# ======================
st.sidebar.title("Spotify Insights")

time_range_display = st.sidebar.selectbox(
    "Select Time Range",
    ["Last Month", "Last 6 Months", "Last Year"]
)

time_range_api = {
    "Last Month": "short_term",
    "Last 6 Months": "medium_term",
    "Last Year": "long_term"
}[time_range_display]

limit = st.sidebar.slider("Select number of results (1–50)", 1, 50, 10)

st.sidebar.header("Filters")
popularity_range = st.sidebar.select_slider(
    "Filter Artists by Popularity",
    options=list(range(0, 101)),
    value=(0, 100)
)

pie_threshold = st.sidebar.slider(
    "Minimum % for Pie Chart Inclusion",
    0.0, 10.0, 1.0, step=0.1
)

st.sidebar.header("Show / Hide Sections")
show_artists = st.sidebar.checkbox("Show Top Artists", True)
show_songs = st.sidebar.checkbox("Show Top Songs", True)
show_artist_pie = st.sidebar.checkbox("Show Artist Concentration", True)
show_genre_pie = st.sidebar.checkbox("Show Genre Distribution", True)
show_popularity = st.sidebar.checkbox("Show Artist Popularity Chart", True)

if st.sidebar.button("Logout"):
    st.session_state.sp = None
    st.session_state.auth_manager.cache_handler.cache.clear()
    st.rerun()

# ======================
# MAIN CONTENT
# ======================
st.title("Your Spotify Listening Stats")

top_artists = get_top_items("artists", limit, time_range_api)
top_tracks = get_top_items("tracks", limit, time_range_api)

# ======================
# ARTISTS TABLE
# ======================
artist_rows = []
for artist in top_artists:
    info = get_artist_info(artist["id"])
    if popularity_range[0] <= info["Popularity"] <= popularity_range[1]:
        artist_rows.append([
            info["Name"],
            info["Followers"],
            info["Popularity"],
            info["Genres"]
        ])

artist_df = pd.DataFrame(
    artist_rows,
    columns=["Artist", "Followers", "Popularity", "Genres"]
)

if show_artists and not artist_df.empty:
    artist_df.insert(0, "Rank", range(1, len(artist_df) + 1))
    st.header(f"Top Artists ({time_range_display})")
    st.dataframe(artist_df, hide_index=True, use_container_width=True)

    st.download_button(
        "Export Artists to CSV",
        artist_df.to_csv(index=False),
        file_name=f"spotify_top_artists_{time_range_api}.csv"
    )

# ======================
# TRACKS TABLE
# ======================
track_rows = []
for track in top_tracks:
    track_rows.append([
        track["name"],
        track["artists"][0]["name"],
        format_duration_ms(track["duration_ms"])
    ])

track_df = pd.DataFrame(
    track_rows,
    columns=["Song", "Artist", "Duration"]
)

if show_songs and not track_df.empty:
    track_df.insert(0, "Rank", range(1, len(track_df) + 1))
    st.header(f"Top Songs ({time_range_display})")
    st.dataframe(track_df, hide_index=True, use_container_width=True)

    st.download_button(
        "Export Songs to CSV",
        track_df.to_csv(index=False),
        file_name=f"spotify_top_songs_{time_range_api}.csv"
    )

# ======================
# POPULARITY BAR CHART
# ======================
if show_popularity and not artist_df.empty:
    st.header("Artist Popularity Comparison")
    chart_df = artist_df.sort_values("Rank")

    st.bar_chart(
        data=chart_df,
        x="Rank",
        y="Popularity"
    )

# ======================
# ARTIST PIE CHART
# ======================
if show_artist_pie and top_tracks:
    st.header("Artist Concentration in Your Top Songs")
    artist_counts = Counter(t["artists"][0]["name"] for t in top_tracks)
    total = sum(artist_counts.values())

    filtered = {
        k: v for k, v in artist_counts.items()
        if (v / total) * 100 >= pie_threshold
    }

    if filtered:
        st.plotly_chart({
            "data": [{
                "type": "pie",
                "labels": list(filtered.keys()),
                "values": list(filtered.values()),
                "hole": 0.4
            }]
        })

# ======================
# GENRE PIE CHART
# ======================
if show_genre_pie and top_artists:
    st.header("Genre Distribution")
    genres = []
    for artist in top_artists:
        genres.extend(artist["genres"])

    genre_counts = Counter(genres)
    if genre_counts:
        st.plotly_chart({
            "data": [{
                "type": "pie",
                "labels": list(genre_counts.keys()),
                "values": list(genre_counts.values()),
                "hole": 0.4
            }]
        })

# ======================
# EXPORT ALL DATA
# ======================
if top_artists and top_tracks:
    with st.expander("Export All Data", expanded=True):
        buffer = StringIO()
        buffer.write("# SPOTIFY LISTENING STATS\n\n")
        buffer.write(f"# Time Range: {time_range_display}\n")
        buffer.write(f"# Exported: {datetime.now()}\n\n")

        artist_df.to_csv(buffer, index=False)
        buffer.write("\n")
        track_df.to_csv(buffer, index=False)

        st.download_button(
            "Export All Data to CSV",
            buffer.getvalue(),
            file_name=f"spotify_listening_data_{time_range_api}.csv"
        )

# ======================
# ABOUT
# ======================
with st.expander("About Time Ranges"):
    st.info("""
    **Last Month** — ~4 weeks  
    **Last 6 Months** — medium-term listening  
    **Last Year** — long-term listening habits
    """)
