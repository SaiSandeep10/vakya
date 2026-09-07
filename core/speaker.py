"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
core/speaker.py

Handles:
  - Text-to-Speech via Piper TTS (fully offline, runs on CPU)
  - Audio playback via sounddevice
  - Non-blocking speech queue so VAKYA can talk without freezing the pipeline
"""

import io
import queue
import struct
import subprocess
import threading
import time
from pathlib import Path

import sounddevice as sd
import numpy as np

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

# Path to the Piper executable (after you install it)
# Download from: https://github.com/rhasspy/piper/releases
PIPER_EXECUTABLE  = r"C:\Users\SAI SANDEEP SADHU\OneDrive\Desktop\vakya\piper\piper\piper.exe"

# Path to the voice model (.onnx) and its config (.onnx.json)
# Download "en_GB-ryan-high" from: https://github.com/rhasspy/piper/blob/master/VOICES.md
VOICE_MODEL       = r"C:\Users\SAI SANDEEP SADHU\OneDrive\Desktop\vakya\piper\voices\en_US-ryan-high.onnx"

SAMPLE_RATE       = 22050    # Ryan voice outputs at 22050 Hz
CHANNELS          = 1
SPEAKING_RATE     = 1.0      # 1.0 = normal, 1.1 = slightly faster

# Intro chime — short beep to signal VAKYA is about to speak
PLAY_CHIME        = True
CHIME_FREQ        = 880      # Hz
CHIME_DURATION    = 0.12     # seconds


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _generate_chime(freq: float, duration: float, sample_rate: int) -> np.ndarray:
    """Generate a short sine wave chime as a numpy array."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = 0.3 * np.sin(2 * np.pi * freq * t)
    # Fade out to avoid clicks
    fade = np.linspace(1.0, 0.0, len(wave))
    return (wave * fade).astype(np.float32)


def _parse_wav_to_array(wav_bytes: bytes) -> np.ndarray:
    """
    Parse raw WAV bytes from Piper stdout into a float32 numpy array.
    Piper outputs 16-bit PCM WAV.
    """
    # Skip the 44-byte WAV header
    pcm = wav_bytes[44:]
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return samples / 32768.0    # normalise to [-1.0, 1.0]


def _synthesise(text: str) -> np.ndarray | None:
    """
    Call Piper as a subprocess and return audio as float32 array.
    Returns None if synthesis fails.
    """
    try:
        result = subprocess.run(
            [
                PIPER_EXECUTABLE,
                "--model",  VOICE_MODEL,
                "--output_raw",           # raw PCM output (faster than file)
                "--length_scale", str(1.0 / SPEAKING_RATE),
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"[VAKYA Speaker] Piper error: {result.stderr.decode()}")
            return None

        # Piper with --output_raw gives raw 16-bit PCM, no WAV header
        raw_pcm = result.stdout
        samples = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32)
        return samples / 32768.0

    except FileNotFoundError:
        print(f"[VAKYA Speaker] ERROR: Piper not found at {PIPER_EXECUTABLE}")
        print("[VAKYA Speaker] Download from https://github.com/rhasspy/piper/releases")
        return None
    except subprocess.TimeoutExpired:
        print("[VAKYA Speaker] ERROR: Piper timed out.")
        return None


# ──────────────────────────────────────────────
# SPEAKER CLASS
# ──────────────────────────────────────────────

class Speaker:
    """
    Non-blocking text-to-speech speaker.

    Accepts text via speak(), synthesises in a background thread,
    and plays through the default audio output device.

    Usage:
        speaker = Speaker()
        speaker.speak("Hello. I am V.A.K.Y.A, your personal assistant.")
        # returns immediately — audio plays in background
        speaker.wait()   # optional: block until speech finishes
    """

    def __init__(self):
        print("[VAKYA] Initialising Speaker...")

        self._queue      = queue.Queue()
        self._is_playing = threading.Event()
        self._chime      = _generate_chime(CHIME_FREQ, CHIME_DURATION, SAMPLE_RATE)

        # Start background synthesis + playback thread
        t = threading.Thread(target=self._playback_loop, daemon=True)
        t.start()

        print(f"[VAKYA] Speaker ready. Voice: en_GB-ryan-high")

    # ── PUBLIC API ──────────────────────────────

    def speak(self, text: str):
        """
        Queue text for speech. Non-blocking.
        VAKYA will speak it as soon as the current utterance finishes.
        """
        if not text or not text.strip():
            return
        print(f"[VAKYA] Speaking: \"{text[:60]}{'...' if len(text) > 60 else ''}\"")
        self._queue.put(text.strip())

    def speak_blocking(self, text: str):
        """Speak text and wait until it finishes before returning."""
        self.speak(text)
        self.wait()

    def wait(self):
        """Block until the speech queue is empty and playback finishes."""
        self._queue.join()
        # Also wait for the is_playing event to clear
        while self._is_playing.is_set():
            time.sleep(0.05)

    def is_speaking(self) -> bool:
        """Returns True if VAKYA is currently speaking."""
        return self._is_playing.is_set() or not self._queue.empty()

    def clear(self):
        """Immediately clear all queued speech."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    # ── INTERNAL ────────────────────────────────

    def _playback_loop(self):
        """
        Runs forever in a background thread.
        Picks text from the queue → synthesises → plays audio.
        """
        while True:
            text = self._queue.get()    # blocks until something is queued

            self._is_playing.set()

            try:
                # Optional chime before speaking
                if PLAY_CHIME:
                    sd.play(self._chime, samplerate=SAMPLE_RATE)
                    sd.wait()

                # Synthesise via Piper
                audio = _synthesise(text)

                if audio is not None and len(audio) > 0:
                    sd.play(audio, samplerate=SAMPLE_RATE)
                    sd.wait()   # wait for this utterance to finish
                else:
                    # Fallback: print to console if Piper not yet installed
                    print(f"[VAKYA FALLBACK] → {text}")

            except Exception as e:
                print(f"[VAKYA Speaker] Playback error: {e}")

            finally:
                self._is_playing.clear()
                self._queue.task_done()


# ──────────────────────────────────────────────
# STARTUP PHRASES — called by main.py on boot
# ──────────────────────────────────────────────

BOOT_PHRASES = [
    "V.A.K.Y.A online. Voice Activated Knowledge Yantric Agent, at your service.",
    "All systems nominal. How can I help you?",
]

READY_PHRASE  = "Listening."
ERROR_PHRASE  = "I encountered an error. Please try again."
THINKING_PHRASE = "Let me think about that."


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run:  python core/speaker.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import random

    speaker = Speaker()

    print("\n[TEST] Testing VAKYA Speaker...")
    print("[TEST] Note: If Piper is not installed yet, text will print to console.\n")

    test_phrases = [
        "V.A.K.Y.A online. Voice Activated Knowledge Yantric Agent, at your service.",
        "I can answer your questions, control your music, and set reminders.",
        "My brain runs entirely on your machine. No cloud. No subscription. No limits.",
        "Say the wake word at any time to speak with me.",
    ]

    for phrase in test_phrases:
        speaker.speak(phrase)
        time.sleep(0.2)     # small gap between phrases

    speaker.wait()
    print("\n[TEST] Speaker test complete.")