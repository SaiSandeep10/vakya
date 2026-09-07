"""VAKYA Full Connectivity Audit Script — run once to check all systems."""
import os
import sys
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv()

PASS = "OK"
FAIL = "MISSING"
results = []

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    msg = f"  [{status}] {label}"
    if detail:
        msg += f"  ({detail})"
    results.append((status, msg))
    print(msg)

print()
print("=" * 55)
print("  V.A.K.Y.A  --  FULL CONNECTIVITY AUDIT")
print("=" * 55)
print()

# ── 1. API Keys ──────────────────────────────────────
print("[A] API Keys")
groq_key = os.getenv("GROQ_API_KEY", "")
check("Groq API key",      bool(groq_key),  f"length={len(groq_key)}")
check("Spotify Client ID", bool(os.getenv("SPOTIFY_CLIENT_ID")))
check("Spotify Secret",    bool(os.getenv("SPOTIFY_CLIENT_SECRET")))
print()

# ── 2. Files & Paths ────────────────────────────────
print("[B] Files & Executables")
ROOT  = Path(__file__).parent
piper = ROOT / "piper" / "piper" / "piper.exe"
voice = ROOT / "piper" / "voices" / "en_US-ryan-high.onnx"
vjson = ROOT / "piper" / "voices" / "en_US-ryan-high.onnx.json"
vlc   = Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe")

check("piper.exe",            piper.exists(), str(piper))
check("en_US-ryan-high.onnx", voice.exists(), str(voice))
check("en_US-ryan-high.onnx.json", vjson.exists())
check("VLC.exe",              vlc.exists(),   str(vlc))
print()

# ── 3. Core Modules ─────────────────────────────────
print("[C] Core Modules")
try:
    from core.brain import Brain
    check("core/brain.py imports", True)
except Exception as e:
    check("core/brain.py imports", False, str(e))

try:
    from core.speaker import Speaker, BOOT_PHRASES, READY_PHRASE, THINKING_PHRASE
    check("core/speaker.py imports", True)
except Exception as e:
    check("core/speaker.py imports", False, str(e))

try:
    from core.listener import Listener
    check("core/listener.py imports", True)
except Exception as e:
    check("core/listener.py imports", False, str(e))

try:
    from core.memory import Memory
    m = Memory()
    s = m.stats()
    m.close()
    detail = f"{s['semantic_facts']} facts, {s['semantic_conversations']} convos, {s['semantic_music']} music prefs, {s['pending_reminders']} reminders"
    check("core/memory.py + ChromaDB + SQLite", True, detail)
except Exception as e:
    check("core/memory.py", False, str(e))
print()

# ── 4. MCP Servers ──────────────────────────────────
print("[D] MCP Tool Servers")

try:
    from mcp_servers.youtube_server import YOUTUBE_TOOLS
    check("mcp_servers/youtube_server.py", True, f"{len(YOUTUBE_TOOLS)} tools")
except Exception as e:
    check("mcp_servers/youtube_server.py", False, str(e))

try:
    from mcp_servers.spotify_server import SPOTIFY_TOOLS
    check("mcp_servers/spotify_server.py", True, f"{len(SPOTIFY_TOOLS)} tools")
except Exception as e:
    check("mcp_servers/spotify_server.py", False, str(e))

try:
    from mcp_servers.utility_server import UTILITY_TOOLS
    check("mcp_servers/utility_server.py", True, f"{len(UTILITY_TOOLS)} tools")
except Exception as e:
    check("mcp_servers/utility_server.py", False, str(e))

try:
    from mcp_servers.filesystem_server import FILESYSTEM_TOOLS
    check("mcp_servers/filesystem_server.py", True, f"{len(FILESYSTEM_TOOLS)} tools")
except Exception as e:
    check("mcp_servers/filesystem_server.py", False, str(e))

try:
    from mcp_servers.search_server import SEARCH_TOOLS
    check("mcp_servers/search_server.py", True, f"{len(SEARCH_TOOLS)} tools")
except Exception as e:
    check("mcp_servers/search_server.py", False, str(e))
print()

# ── 5. Tool Registry ────────────────────────────────
print("[E] Tool Registry (main.py TOOL_MAP)")
try:
    from mcp_servers.youtube_server    import YOUTUBE_TOOLS
    from mcp_servers.spotify_server    import SPOTIFY_TOOLS
    from mcp_servers.utility_server    import UTILITY_TOOLS
    from mcp_servers.filesystem_server import FILESYSTEM_TOOLS
    from mcp_servers.search_server     import SEARCH_TOOLS
    ALL = YOUTUBE_TOOLS + SPOTIFY_TOOLS + UTILITY_TOOLS + FILESYSTEM_TOOLS + SEARCH_TOOLS
    TOOL_MAP = {t["name"]: t["function"] for t in ALL}
    check("ALL_TOOLS assembled", True, f"{len(TOOL_MAP)} tools in TOOL_MAP")
    names = list(TOOL_MAP.keys())
    print(f"     {names}")
except Exception as e:
    check("Tool registry assembly", False, str(e))
print()

# ── 6. Summary ──────────────────────────────────────
failed = [r for r in results if r[0] == FAIL]
print("=" * 55)
if not failed:
    print("  ALL SYSTEMS NOMINAL -- VAKYA is ready to run")
else:
    print(f"  {len(failed)} issue(s) found:")
    for _, msg in failed:
        print(f"  {msg}")
print("=" * 55)
print()
