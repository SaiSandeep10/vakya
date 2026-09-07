"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 4 | mcp_servers/spotify_server.py

Spotify MCP Tool Server.
Provides play, pause, skip, volume, search, and now-playing tools
to the VAKYA brain via function calling.

Setup:
  1. Create a Spotify Developer app at developer.spotify.com/dashboard
  2. Add redirect URI: http://127.0.0.1:8888/callback
  3. Add to .env:
       SPOTIFY_CLIENT_ID=your_id
       SPOTIFY_CLIENT_SECRET=your_secret
       SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "playlist-read-private "
    "streaming"
)

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


# ──────────────────────────────────────────────
# SPOTIFY CLIENT
# ──────────────────────────────────────────────

def _get_spotify() -> "spotipy.Spotify | None":
    """Return an authenticated Spotify client or None if not configured."""
    if not SPOTIPY_AVAILABLE:
        print("[Spotify] spotipy not installed. Run: pip install spotipy")
        return None
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[Spotify] Missing credentials in .env file.")
        return None
    try:
        auth = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            open_browser=True,
            cache_path=".spotify_token_cache"
        )
        return spotipy.Spotify(auth_manager=auth)
    except Exception as e:
        print(f"[Spotify] Auth error: {e}")
        return None


# ──────────────────────────────────────────────
# TOOL FUNCTIONS
# ──────────────────────────────────────────────

def spotify_play(track_name: str = "", artist_name: str = "") -> dict:
    """
    Play a song by name and optional artist.
    If no track given, resumes current playback.
    """
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}

    try:
        if not track_name:
            sp.start_playback()
            return {"success": True, "message": "Resuming playback."}

        query = f"track:{track_name}"
        if artist_name:
            query += f" artist:{artist_name}"

        results = sp.search(q=query, type="track", limit=1)
        tracks  = results["tracks"]["items"]

        if not tracks:
            return {"success": False, "message": f"Could not find '{track_name}'."}

        track   = tracks[0]
        uri     = track["uri"]
        name    = track["name"]
        artist  = track["artists"][0]["name"]

        sp.start_playback(uris=[uri])
        return {
            "success": True,
            "message": f"Playing {name} by {artist}.",
            "track":   name,
            "artist":  artist
        }

    except spotipy.exceptions.SpotifyException as e:
        if "Premium" in str(e):
            return {"success": False, "message": "Spotify Premium required for playback control."}
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_pause() -> dict:
    """Pause current playback."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        sp.pause_playback()
        return {"success": True, "message": "Playback paused."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_next() -> dict:
    """Skip to next track."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        sp.next_track()
        return {"success": True, "message": "Skipped to next track."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_previous() -> dict:
    """Go back to previous track."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        sp.previous_track()
        return {"success": True, "message": "Playing previous track."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_volume(percent: int) -> dict:
    """Set volume. percent must be 0–100."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        percent = max(0, min(100, int(percent)))
        sp.volume(percent)
        return {"success": True, "message": f"Volume set to {percent} percent."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_now_playing() -> dict:
    """Return information about the currently playing track."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        current = sp.current_playback()
        if not current or not current.get("item"):
            return {"success": True, "message": "Nothing is playing right now."}

        track  = current["item"]["name"]
        artist = current["item"]["artists"][0]["name"]
        album  = current["item"]["album"]["name"]
        is_playing = current["is_playing"]

        return {
            "success":    True,
            "message":    f"{'Playing' if is_playing else 'Paused'}: {track} by {artist} from {album}.",
            "track":      track,
            "artist":     artist,
            "album":      album,
            "is_playing": is_playing
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def spotify_play_playlist(playlist_name: str) -> dict:
    """Play a playlist by name from the user's library."""
    sp = _get_spotify()
    if not sp:
        return {"success": False, "message": "Spotify not configured."}
    try:
        playlists = sp.current_user_playlists(limit=50)
        match = None
        for pl in playlists["items"]:
            if playlist_name.lower() in pl["name"].lower():
                match = pl
                break

        if not match:
            return {"success": False, "message": f"Playlist '{playlist_name}' not found."}

        sp.start_playback(context_uri=match["uri"])
        return {"success": True, "message": f"Playing playlist: {match['name']}."}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ──────────────────────────────────────────────
# TOOL DEFINITIONS — for brain.py tool calling
# ──────────────────────────────────────────────

SPOTIFY_TOOLS = [
    {
        "name":        "spotify_play",
        "description": "Play a song on Spotify by track name and optional artist name. Also resumes paused playback if no track given.",
        "function":    spotify_play,
        "parameters":  {"track_name": str, "artist_name": str}
    },
    {
        "name":        "spotify_pause",
        "description": "Pause the currently playing Spotify track.",
        "function":    spotify_pause,
        "parameters":  {}
    },
    {
        "name":        "spotify_next",
        "description": "Skip to the next track on Spotify.",
        "function":    spotify_next,
        "parameters":  {}
    },
    {
        "name":        "spotify_previous",
        "description": "Go back to the previous track on Spotify.",
        "function":    spotify_previous,
        "parameters":  {}
    },
    {
        "name":        "spotify_volume",
        "description": "Set Spotify playback volume. percent is an integer from 0 to 100.",
        "function":    spotify_volume,
        "parameters":  {"percent": int}
    },
    {
        "name":        "spotify_now_playing",
        "description": "Find out what song is currently playing on Spotify.",
        "function":    spotify_now_playing,
        "parameters":  {}
    },
    {
        "name":        "spotify_play_playlist",
        "description": "Play one of the user's Spotify playlists by name.",
        "function":    spotify_play_playlist,
        "parameters":  {"playlist_name": str}
    },
]


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python mcp_servers/spotify_server.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] Spotify Server — testing now playing...")
    result = spotify_now_playing()
    print(json.dumps(result, indent=2))

    print("\n[TEST] Searching for a track...")
    result = spotify_play("Vande Mataram", "AR Rahman")
    print(json.dumps(result, indent=2))