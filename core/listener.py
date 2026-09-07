"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 1 | core/listener.py

Handles:
  - Wake word detection via OpenWakeWord
  - Audio recording via PyAudio
  - Speech-to-text transcription via Faster-Whisper (CUDA / RTX 3050)
"""

import time
import queue
import threading
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
from openwakeword.model import Model as WakeWordModel

# ──────────────────────────────────────────────
# CONFIG  (mirrors config.yaml values)
# ──────────────────────────────────────────────
WAKE_WORD_MODEL     = "alexa"               # built-in OWW model used until Week 6
                                            # In Week 6 we train & swap in "hey_vakya"
WAKE_WORD_THRESHOLD = 0.7                   # confidence required to trigger
SILENCE_TIMEOUT     = 1.5                   # seconds of silence = end of utterance
MAX_RECORD_SECONDS  = 15                    # hard cap on recording length
MIC_DEVICE_INDEX    = 2       # Microphone Array (Realtek) — change if mic changes
WHISPER_MODEL_SIZE  = "small"              # tiny / base / small / medium / large
WHISPER_DEVICE      = "cuda"               # "cuda" for RTX 3050, "cpu" fallback
WHISPER_COMPUTE     = "float16"            # float16 on GPU, int8 on CPU

SAMPLE_RATE         = 16000               # Hz — required by both Whisper & OWW
CHUNK_SIZE          = 1280                # frames per buffer (80ms at 16kHz)
CHANNELS            = 1
FORMAT              = pyaudio.paInt16

SILENCE_THRESHOLD   = 500                 # RMS below this = silence


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _rms(audio_chunk: bytes) -> float:
    """Root Mean Square of a raw PCM chunk — used to detect silence."""
    samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0


def _frames_to_float32(frames: list[bytes]) -> np.ndarray:
    """Convert raw PCM frames list to float32 array for Whisper."""
    raw = b"".join(frames)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return samples / 32768.0          # normalise to [-1.0, 1.0]


# ──────────────────────────────────────────────
# LISTENER CLASS
# ──────────────────────────────────────────────

class Listener:
    """
    Listens continuously for the VAKYA wake word.
    Once triggered, records the user's utterance until silence,
    then transcribes it and returns the text.

    Usage:
        listener = Listener()
        listener.start()

        while True:
            text = listener.get_transcription()   # blocks until something is said
            print(f"User said: {text}")
    """

    def __init__(self):
        print("[VAKYA] Initialising Listener...")

        # PyAudio stream
        self._pa       = pyaudio.PyAudio()
        self._stream   = None

        # Thread-safe queue: wake word thread → recording thread
        self._trigger_event  = threading.Event()
        self._result_queue   = queue.Queue()

        # Load wake word model
        print(f"[VAKYA] Loading wake word model: {WAKE_WORD_MODEL}")
        self._oww = WakeWordModel(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx"
        )

        # Load Whisper model (downloads once, cached afterward)
        print(f"[VAKYA] Loading Whisper '{WHISPER_MODEL_SIZE}' on {WHISPER_DEVICE}...")
        self._whisper = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        )

        self._running = False
        print("[VAKYA] Listener ready.")

    # ── PUBLIC API ──────────────────────────────

    def start(self):
        """Start background listening thread. Non-blocking."""
        self._running = True
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()
        print("[VAKYA] Listening for wake word...")

    def stop(self):
        """Gracefully stop the listener."""
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._pa.terminate()
        print("[VAKYA] Listener stopped.")

    def get_transcription(self, timeout: float = None) -> str | None:
        """
        Blocking call. Returns transcribed text when the user
        finishes speaking after the wake word, or None on timeout.
        """
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── INTERNAL LOOP ───────────────────────────

    def _listen_loop(self):
        """
        Main loop — runs in a background thread.

        Phase 1: Wake word detection  (always active)
        Phase 2: Record utterance     (triggered after wake word)
        Phase 3: Transcribe           (after silence detected)
        """
        self._stream = self._pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=MIC_DEVICE_INDEX,
        frames_per_buffer=CHUNK_SIZE
        )

        while self._running:

            # ── PHASE 1: Wake Word Detection ──────────────
            chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_int16 = np.frombuffer(chunk, dtype=np.int16)

            prediction = self._oww.predict(audio_int16)
            score = prediction.get(WAKE_WORD_MODEL, 0.0)

            if score < WAKE_WORD_THRESHOLD:
                continue    # still waiting — loop back

            # Wake word confirmed
            print(f"\n[VAKYA] Wake word detected (confidence: {score:.2f})")
            print("[VAKYA] Listening for command...")

            # ── PHASE 2: Record Until Silence ─────────────
            frames          = []
            silent_chunks   = 0
            max_chunks      = int(SAMPLE_RATE / CHUNK_SIZE * MAX_RECORD_SECONDS)
            silence_chunks_needed = int(SILENCE_TIMEOUT / (CHUNK_SIZE / SAMPLE_RATE))

            for _ in range(max_chunks):
                chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(chunk)

                rms = _rms(chunk)
                if rms < SILENCE_THRESHOLD:
                    silent_chunks += 1
                else:
                    silent_chunks = 0   # reset on any sound

                if silent_chunks >= silence_chunks_needed:
                    break               # user finished speaking

            if not frames:
                print("[VAKYA] No audio captured. Resuming wake word detection.")
                continue

            # ── PHASE 3: Transcribe ───────────────────────
            print("[VAKYA] Transcribing...")
            audio_float32 = _frames_to_float32(frames)

            segments, info = self._whisper.transcribe(
                audio_float32,
                language="en",
                beam_size=5,
                vad_filter=True,          # removes silence from transcript
                vad_parameters={
                    "min_silence_duration_ms": 300
                }
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()

            if text:
                print(f"[VAKYA] Transcribed: \"{text}\"")
                self._result_queue.put(text)
            else:
                print("[VAKYA] Empty transcription — resuming.")

            # Reset OWW state to avoid echo-triggering
            self._oww.reset()


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run:  python core/listener.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    listener = Listener()
    listener.start()

    print("\n[TEST] Say 'Alexa' (placeholder wake word) followed by a command.")
    print("[TEST] In Week 6 this will be replaced with your custom 'Hey VAKYA' model.")
    print("[TEST] Press Ctrl+C to quit.\n")

    try:
        while True:
            result = listener.get_transcription(timeout=30)
            if result:
                print(f"\n{'='*50}")
                print(f"  RESULT: {result}")
                print(f"{'='*50}\n")
    except KeyboardInterrupt:
        listener.stop()
        print("[TEST] Done.")