"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 4 Extra | mcp_servers/youtube_server.py

YouTube Music MCP Tool Server.
Uses yt-dlp to search and stream any song by name.
Uses VLC to play the audio — no browser, no GUI.

Requirements:
  pip install yt-dlp
  Install VLC: https://www.videolan.org/vlc/
"""

import json
import subprocess
import threading
import time
from pathlib import Path

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

VLC_PATH      = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
AUDIO_FORMAT  = "bestaudio/best"
YT_SEARCH_URL = "ytsearch1:"

# ──────────────────────────────────────────────
# PLAYER STATE
# ──────────────────────────────────────────────

_vlc_process: subprocess.Popen | None = None
_current_track: dict = {}
_lock = threading.Lock()


def _stop_vlc():
    """Kill any running VLC process."""
    global _vlc_process
    with _lock:
        if _vlc_process and _vlc_process.poll() is None:
            _vlc_process.terminate()
            try:
                _vlc_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _vlc_process.kill()
        _vlc_process = None


def _get_stream_url(query: str) -> tuple[str, str] | tuple[None, None]:
    """
    Use yt-dlp to find the direct audio stream URL and title.
    Returns (url, title) or (None, None) on failure.
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--get-url",
                "--get-title",
                "--format", AUDIO_FORMAT,
                "--no-warnings",
                "--quiet",
                f"{YT_SEARCH_URL}{query}"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        lines = result.stdout.strip().splitlines()

        if len(lines) >= 2:
            if lines[0].startswith("http"):
                url, title = lines[0], lines[1]
            else:
                title, url = lines[0], lines[1]
            return url, title

        return None, None

    except subprocess.TimeoutExpired:
        print("[YouTube] yt-dlp search timed out.")
        return None, None
    except FileNotFoundError:
        print("[YouTube] yt-dlp not found. Run: pip install yt-dlp")
        return None, None
    except Exception as e:
        print(f"[YouTube] Search error: {e}")
        return None, None


# ──────────────────────────────────────────────
# TOOL FUNCTIONS
# ──────────────────────────────────────────────

def youtube_play(song_name: str, artist_name: str = "") -> dict:
    """Search YouTube Music for a song and play it via VLC."""
    global _vlc_process, _current_track

    if not Path(VLC_PATH).exists():
        return {
            "success": False,
            "message": f"VLC not found. Please install VLC from videolan.org."
        }

    query = song_name.strip()
    if artist_name:
        query += f" {artist_name.strip()}"
    query += " official audio"

    print(f"[YouTube] Searching: {query}")
    url, title = _get_stream_url(query)

    if not url:
        return {
            "success": False,
            "message": f"Could not find '{song_name}' on YouTube. Please try a different search."
        }

    _stop_vlc()

    try:
        with _lock:
            _vlc_process = subprocess.Popen(
                [
                    VLC_PATH,
                    "--no-video",
                    "--play-and-exit",
                    "--qt-start-minimized",   # minimised window, not hidden
                    url
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        _current_track = {"title": title or song_name, "url": url}

        display_name = (title if title else song_name)[:60]
        print(f"[YouTube] Playing: {display_name}")

        return {
            "success": True,
            "message": f"Playing {display_name}.",
            "title":   display_name
        }

    except Exception as e:
        return {"success": False, "message": f"Playback error: {e}"}


def youtube_stop() -> dict:
    """Stop current YouTube Music playback."""
    global _current_track

    if not _vlc_process or _vlc_process.poll() is not None:
        return {"success": False, "message": "Nothing is playing right now."}

    _stop_vlc()
    _current_track = {}
    return {"success": True, "message": "Playback stopped."}


def youtube_now_playing() -> dict:
    """Return info about what is currently playing."""
    if not _vlc_process or _vlc_process.poll() is not None:
        return {"success": True, "message": "Nothing is playing right now."}

    title = _current_track.get("title", "Unknown track")
    return {"success": True, "message": f"Currently playing: {title}.", "title": title}


def youtube_volume(percent: int) -> dict:
    """Set system volume on Windows. percent is 0 to 100."""
    percent = max(0, min(100, int(percent)))
    try:
        # PowerShell one-liner to set system volume
        ps_command = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "
            f"$steps = [Math]::Round({percent} / 2); "
            f"1..$steps | ForEach-Object {{ $obj.SendKeys([char]175) }}"
        )
        subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            timeout=10
        )
        return {"success": True, "message": f"Volume set to {percent} percent."}
    except Exception as e:
        return {"success": False, "message": f"Could not set volume: {e}"}


# ──────────────────────────────────────────────
# TOOL DEFINITIONS
# ──────────────────────────────────────────────

YOUTUBE_TOOLS = [
    {
        "name":        "youtube_play",
        "description": "Search YouTube Music and play a song by name. Optionally provide artist name for better accuracy.",
        "function":    youtube_play,
        "parameters":  {"song_name": str, "artist_name": str}
    },
    {
        "name":        "youtube_stop",
        "description": "Stop the currently playing YouTube Music track.",
        "function":    youtube_stop,
        "parameters":  {}
    },
    {
        "name":        "youtube_now_playing",
        "description": "Find out what song is currently playing from YouTube Music.",
        "function":    youtube_now_playing,
        "parameters":  {}
    },
    {
        "name":        "youtube_volume",
        "description": "Set the system volume. percent is an integer from 0 to 100.",
        "function":    youtube_volume,
        "parameters":  {"percent": int}
    },
]


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python mcp_servers/youtube_server.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] YouTube Music Server\n")

    print("[TEST] Playing AR Rahman — Vande Mataram...")
    result = youtube_play("Vande Mataram", "AR Rahman")
    print(json.dumps(result, indent=2))

    if result["success"]:
        print("\n[TEST] Playing for 30 seconds...")
        time.sleep(30)

        print("\n[TEST] Now playing:")
        print(json.dumps(youtube_now_playing(), indent=2))

        print("\n[TEST] Stopping...")
        print(json.dumps(youtube_stop(), indent=2))

    print("\n[TEST] Done.")