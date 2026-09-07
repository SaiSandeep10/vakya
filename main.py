"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 5 Final | main.py

All modules:
  - listener.py          — wake word + STT
  - brain.py             — Groq LLM
  - speaker.py           — Piper TTS
  - memory.py            — ChromaDB + SQLite
  - youtube_server.py    — YouTube Music (working)
  - spotify_server.py    — Spotify (when credentials added)
  - utility_server.py    — timers, reminders, calculator
  - filesystem_server.py — local file search
  - search_server.py     — DuckDuckGo web search

Fixes in this version:
  - Robust JSON tool call parser (handles all edge cases)
  - Direct music trigger — bypasses brain for play commands
  - Direct sports/match trigger — always does live search
  - Direct weather/news triggers
"""

import re
import sys
import time
import json
import threading

from core.listener import Listener
from core.brain    import Brain
from core.speaker  import Speaker, BOOT_PHRASES, READY_PHRASE, THINKING_PHRASE
from core.memory   import Memory

from mcp_servers.youtube_server    import YOUTUBE_TOOLS, youtube_play, youtube_stop, youtube_now_playing
from mcp_servers.spotify_server    import SPOTIFY_TOOLS
from mcp_servers.utility_server    import UTILITY_TOOLS, set_timer_callback, get_current_time
from mcp_servers.filesystem_server import FILESYSTEM_TOOLS
from mcp_servers.search_server     import SEARCH_TOOLS, search_weather, search_news, web_search

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

SHOW_TRANSCRIPT    = True
SHOW_RESPONSE      = True
REMINDER_CHECK_SEC = 30

# ──────────────────────────────────────────────
# TOOL REGISTRY
# ──────────────────────────────────────────────

ALL_TOOLS = YOUTUBE_TOOLS + SPOTIFY_TOOLS + UTILITY_TOOLS + FILESYSTEM_TOOLS + SEARCH_TOOLS
TOOL_MAP  = {tool["name"]: tool["function"] for tool in ALL_TOOLS}


def _build_tool_descriptions() -> str:
    lines = [
        "You have access to these tools.",
        'To call a tool respond ONLY with JSON: {"tool": "<name>", "params": {<params>}}',
        "If no tool is needed, respond in plain conversational text.",
        ""
    ]
    for tool in ALL_TOOLS:
        params = ", ".join(
            f"{k}: {v.__name__}" for k, v in tool["parameters"].items()
        ) if tool["parameters"] else "none"
        lines.append(f"- {tool['name']}({params}): {tool['description']}")
    return "\n".join(lines)


TOOL_DESCRIPTIONS = _build_tool_descriptions()


def _try_execute_tool(response_text: str) -> str | None:
    """
    Robustly check if brain responded with a tool call JSON and execute it.
    Handles JSON embedded anywhere in the response text.
    """
    response_text = response_text.strip()

    # Strategy 1 — entire response is JSON
    try:
        call = json.loads(response_text)
        if "tool" in call:
            name   = call.get("tool", "")
            params = call.get("params", {})
            if name in TOOL_MAP:
                result = TOOL_MAP[name](**params)
                return result.get("message", "Done.")
    except json.JSONDecodeError:
        pass

    # Strategy 2 — JSON block somewhere inside the response
    try:
        start    = response_text.index("{")
        end      = response_text.rindex("}") + 1
        json_str = response_text[start:end]
        call     = json.loads(json_str)
        if "tool" in call:
            name   = call.get("tool", "")
            params = call.get("params", {})
            if name in TOOL_MAP:
                result = TOOL_MAP[name](**params)
                return result.get("message", "Done.")
    except (ValueError, json.JSONDecodeError, KeyError):
        pass

    # Strategy 3 — regex fallback for malformed JSON
    try:
        tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', response_text)
        if tool_match:
            name = tool_match.group(1)
            if name in TOOL_MAP:
                # Try to extract params
                params_match = re.search(r'"params"\s*:\s*(\{[^}]*\})', response_text)
                params = {}
                if params_match:
                    try:
                        params = json.loads(params_match.group(1))
                    except Exception:
                        pass
                result = TOOL_MAP[name](**params)
                return result.get("message", "Done.")
    except Exception:
        pass

    return None


def _speak_long_text(speaker: Speaker, text: str, max_chars: int = 500):
    """
    Speak a long text in a natural summarised form.
    Cuts at sentence boundary to avoid mid-sentence cutoff.
    """
    if len(text) <= max_chars:
        speaker.speak(text)
        return

    truncated   = text[:max_chars]
    last_period = max(truncated.rfind(". "), truncated.rfind(".\n"))
    if last_period > 100:
        truncated = truncated[:last_period + 1]

    speaker.speak(truncated)
    speaker.speak("Say search more if you want additional details.")


def _extract_song_name(text_lower: str) -> str:
    """Extract song name from a play command."""
    for prefix in ["please play ", "can you play ", "put on ", "play me ", "play "]:
        if prefix in text_lower:
            return text_lower.split(prefix, 1)[-1].strip("?. ")
    return text_lower.strip("?. ")


def _extract_location(text_lower: str) -> str:
    """Extract location from a weather query."""
    words = text_lower.replace("?", "").replace(".", "").split()
    for i, w in enumerate(words):
        if w in ("in", "at", "for") and i + 1 < len(words):
            return " ".join(words[i + 1:]).strip()
    return "Bangalore"   # default


def _extract_news_topic(text_lower: str) -> str:
    """Extract topic from a news query."""
    for prefix in ["latest news about", "latest news on", "news about", "news on",
                   "what's happening with", "what happened in", "tell me about"]:
        if prefix in text_lower:
            return text_lower.split(prefix, 1)[-1].strip("?. ")
    return text_lower.strip("?. ")


# ──────────────────────────────────────────────
# REMINDER CHECKER THREAD
# ──────────────────────────────────────────────

def reminder_checker(memory: Memory, speaker: Speaker, stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            due = memory.get_due_reminders()
            for reminder in due:
                msg = f"Reminder: {reminder['label']}"
                print(f"\n[VAKYA] {msg}")
                speaker.speak(msg)
        except Exception as e:
            print(f"[VAKYA Reminder] Error: {e}")
        stop_event.wait(timeout=REMINDER_CHECK_SEC)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print("""
╔══════════════════════════════════════════════╗
║   V.A.K.Y.A                                  ║
║   Voice Activated Knowledge Yantric Agent    ║
║   Built by Sai Sandeep                       ║
╚══════════════════════════════════════════════╝
    """)

    # ── Boot modules ────────────────────────────
    try:
        speaker  = Speaker()
    except Exception as e:
        print(f"[VAKYA] ERROR loading Speaker: {e}"); sys.exit(1)

    try:
        memory   = Memory()
    except Exception as e:
        print(f"[VAKYA] ERROR loading Memory: {e}"); sys.exit(1)

    try:
        brain    = Brain()
    except Exception as e:
        print(f"[VAKYA] ERROR loading Brain: {e}"); sys.exit(1)

    try:
        listener = Listener()
    except Exception as e:
        print(f"[VAKYA] ERROR loading Listener: {e}"); sys.exit(1)

    # Register timer alert callback
    set_timer_callback(lambda msg: speaker.speak(msg))

    # ── Boot sequence ───────────────────────────
    print("\n[VAKYA] All systems online.\n")
    speaker.speak_blocking(BOOT_PHRASES[0])
    speaker.speak_blocking(BOOT_PHRASES[1])

    # ── Reminder checker thread ──────────────────
    stop_event = threading.Event()
    threading.Thread(
        target=reminder_checker,
        args=(memory, speaker, stop_event),
        daemon=True
    ).start()

    # ── Start listening ─────────────────────────
    listener.start()
    print("\n[VAKYA] Waiting for wake word...\n")

    # ── Main loop ───────────────────────────────
    try:
        while True:
            text = listener.get_transcription(timeout=60)
            if not text:
                continue

            if SHOW_TRANSCRIPT:
                print(f"\n[YOU]   {text}")

            text_lower = text.lower().strip()

            # ══════════════════════════════════════
            # SYSTEM COMMANDS
            # ══════════════════════════════════════

            if any(p in text_lower for p in ["goodbye vakya", "shut down", "turn off"]):
                speaker.speak_blocking("Shutting down. Goodbye.")
                break

            if any(p in text_lower for p in ["reset conversation", "clear history", "forget everything"]):
                brain.reset()
                speaker.speak_blocking("Conversation history cleared.")
                continue

            # ══════════════════════════════════════
            # MEMORY COMMANDS
            # ══════════════════════════════════════

            if text_lower.startswith("remember that") or text_lower.startswith("vakya remember"):
                fact = text.split("that", 1)[-1].strip() if "that" in text_lower else text
                memory.remember(fact, category="fact")
                speaker.speak("Got it. I will remember that.")
                speaker.wait()
                speaker.speak(READY_PHRASE)
                continue

            if any(p in text_lower for p in ["list reminders", "show reminders", "what are my reminders"]):
                reminders = memory.list_reminders()
                if not reminders:
                    speaker.speak("You have no pending reminders.")
                else:
                    speaker.speak(f"You have {len(reminders)} reminder{'s' if len(reminders)>1 else ''}.")
                    for r in reminders[:3]:
                        speaker.speak(f"{r['label']} at {r['due_at']}")
                speaker.wait()
                speaker.speak(READY_PHRASE)
                continue

            if "memory stats" in text_lower or "what do you remember" in text_lower:
                stats = memory.stats()
                speaker.speak(
                    f"I have {stats['semantic_facts']} personal facts, "
                    f"{stats['semantic_conversations']} conversation memories, "
                    f"{stats['semantic_music']} music preferences, "
                    f"and {stats['pending_reminders']} pending reminders."
                )
                speaker.wait()
                speaker.speak(READY_PHRASE)
                continue

            # ══════════════════════════════════════
            # DIRECT TRIGGERS — bypass brain entirely
            # ══════════════════════════════════════

            # ── Time ─────────────────────────────
            if any(p in text_lower for p in ["what time", "what's the time", "current time", "what is the time"]):
                result = get_current_time()
                speaker.wait()
                speaker.speak(result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Date ─────────────────────────────
            if any(p in text_lower for p in ["what date", "what's the date", "today's date", "what day is it"]):
                result = get_current_time()
                speaker.wait()
                speaker.speak(result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Music — play ──────────────────────
            if any(p in text_lower for p in ["play ", "put on ", "play me "]):
                song = _extract_song_name(text_lower)
                speaker.speak(f"Searching for {song}.")
                result = youtube_play(song)
                speaker.wait()
                speaker.speak(result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Music — stop ──────────────────────
            if any(p in text_lower for p in ["stop music", "stop the music", "stop playing",
                                              "pause music", "pause the music"]):
                result = youtube_stop()
                speaker.wait()
                speaker.speak(result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Music — now playing ───────────────
            if any(p in text_lower for p in ["what's playing", "what is playing",
                                              "what song is this", "now playing"]):
                result = youtube_now_playing()
                speaker.wait()
                speaker.speak(result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Weather ───────────────────────────
            if any(p in text_lower for p in ["weather", "temperature", "how hot", "how cold", "raining"]):
                location = _extract_location(text_lower)
                speaker.speak(f"Searching weather for {location}.")
                result = search_weather(location)
                speaker.wait()
                _speak_long_text(speaker, result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── News ──────────────────────────────
            if any(p in text_lower for p in ["latest news", "what's happening", "news about",
                                              "news on", "tell me about"]):
                topic = _extract_news_topic(text_lower)
                speaker.speak(f"Searching news about {topic}.")
                result = search_news(topic)
                speaker.wait()
                _speak_long_text(speaker, result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── Sports / Match ────────────────────
            if any(p in text_lower for p in ["match", "score", "ipl", "cricket",
                                              "football", "basketball", "tournament"]):
                speaker.speak("Let me search for that.")
                result = search_news(text)
                speaker.wait()
                _speak_long_text(speaker, result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ── General web search ────────────────
            if any(p in text_lower for p in ["search for", "look up", "find out",
                                              "google", "search the web"]):
                query = text_lower
                for prefix in ["search for", "look up", "find out about",
                                "google", "search the web for"]:
                    if prefix in query:
                        query = query.split(prefix, 1)[-1].strip("?. ")
                        break
                speaker.speak(f"Searching for {query}.")
                result = web_search(query)
                speaker.wait()
                _speak_long_text(speaker, result["message"])
                speaker.speak(READY_PHRASE)
                continue

            # ══════════════════════════════════════
            # BRAIN — for everything else
            # ══════════════════════════════════════

            memory_context = memory.build_context(text)

            if len(text.split()) > 6:
                speaker.speak(THINKING_PHRASE)

            full_context = TOOL_DESCRIPTIONS
            if memory_context:
                full_context += f"\n\n{memory_context}"

            response = brain.think(text, memory_context=full_context)

            if SHOW_RESPONSE:
                print(f"[VAKYA] {response}\n")

            # Try tool execution
            tool_result = _try_execute_tool(response)

            speaker.wait()
            if tool_result:
                print(f"[VAKYA Tools] {tool_result}")
                _speak_long_text(speaker, tool_result)
            else:
                speaker.speak(response)

            # Save to memory
            memory.remember_conversation(text, tool_result or response)

            # Ready signal
            time.sleep(0.5)
            speaker.wait()
            speaker.speak(READY_PHRASE)

    except KeyboardInterrupt:
        print("\n[VAKYA] Interrupted.")

    finally:
        stop_event.set()
        listener.stop()
        speaker.wait()
        memory.close()
        print("[VAKYA] Goodbye.")


if __name__ == "__main__":
    main()