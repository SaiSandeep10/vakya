# V.A.K.Y.A

**Voice Activated Knowledge Yantric Agent** — a Windows voice assistant built with OpenWakeWord, Faster-Whisper, Groq, Piper TTS, and local memory.

## Features

- Wake-word detection with OpenWakeWord (`alexa`)
- Speech-to-text using Faster-Whisper (`small`, CUDA/`float16` by default)
- Groq-powered conversation using `allam-2-7b`
- Offline speech output through Piper and the `en_US-ryan-high` voice
- Persistent semantic memory (ChromaDB) and reminders/facts (SQLite)
- YouTube playback through `yt-dlp` and VLC
- Optional Spotify control
- Web search, weather, news, timers, reminders, calculations, unit conversion, and safe local-file tools

## Requirements

- Windows
- Python 3.10 or later
- An NVIDIA GPU with CUDA support for the default speech-to-text settings, or update `core/listener.py` to use `cpu` and `int8`
- A [Groq API key](https://console.groq.com/keys)
- Piper for Windows and the `en_US-ryan-high.onnx` voice model
- VLC, if you want YouTube playback

## Setup

1. Create and activate a virtual environment:

   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install Python dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root:

   ```ini
   GROQ_API_KEY=gsk_your_key_here

   # Optional: required only for Spotify controls
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

4. Install the non-Python audio tools:

   - Install [Piper](https://github.com/rhasspy/piper/releases) and place its executable where `PIPER_EXECUTABLE` in `core/speaker.py` points.
   - Download the `en_US-ryan-high.onnx` voice and place it in `piper/voices/`, alongside its `.onnx.json` configuration file.
   - Install [VLC](https://www.videolan.org/vlc/) at the default Windows location for YouTube playback.
   - Ensure `yt-dlp` is available on your `PATH` (the package is included in `requirements.txt`).

5. Check the machine-specific settings in the source files before running:

   - `core/listener.py`: `MIC_DEVICE_INDEX`, Whisper device, and compute type.
   - `core/speaker.py`: `PIPER_EXECUTABLE` and `VOICE_MODEL`.
   - `mcp_servers/youtube_server.py`: `VLC_PATH` if VLC is installed elsewhere.

6. Start VAKYA:

   ```powershell
   python main.py
   ```

Say **“Alexa”**, then speak your request. Press `Ctrl+C` to stop it.

## Example commands

| Say | Result |
| --- | --- |
| “What time is it?” | Speaks the current date and time. |
| “Play Bohemian Rhapsody” | Searches YouTube and plays the result through VLC. |
| “Stop music” | Stops the current YouTube playback. |
| “What’s the weather in Colombo?” | Retrieves current weather. |
| “Latest news about space” | Searches recent news. |
| “Search for Python virtual environments” | Performs a web search. |
| “Remember that I am allergic to peanuts” | Stores a semantic memory. |
| “List reminders” | Reads pending reminders. |
| “What do you remember?” | Reports memory statistics. |
| “Reset conversation” | Clears only the in-memory LLM conversation history. |
| “Goodbye VAKYA” | Shuts down cleanly. |

## Project layout

```text
vakya/
├── main.py                     # Application entry point and voice-command routing
├── core/
│   ├── listener.py              # Wake word, microphone capture, and transcription
│   ├── speaker.py               # Piper synthesis and audio playback
│   ├── brain.py                 # Groq client and conversation history
│   └── memory.py                # ChromaDB and SQLite persistence
├── mcp_servers/
│   ├── youtube_server.py        # YouTube search and VLC playback
│   ├── spotify_server.py        # Spotify Web API controls
│   ├── utility_server.py        # Timers, reminders, calculations, conversions
│   ├── filesystem_server.py     # Restricted file search, read, and listing
│   └── search_server.py         # Web, weather, and news search
├── piper/voices/                # Piper voice model assets
├── data/                        # Created at runtime; local memory databases
├── requirements.txt
└── .env                         # Local secrets; do not commit
```

## Notes

- The active runtime settings are defined directly in the Python modules. `config.yaml` is currently not read by the application and does not control the running configuration.
- The file tools are restricted to Desktop, Documents, Downloads, OneDrive, Music, and Pictures.
- `Reset conversation` does not erase ChromaDB or SQLite data. Remove the relevant files under `data/` only if you intentionally want to erase persisted memory.
- `.env`, Spotify tokens, Piper model binaries, and local memory data are ignored by Git.

## Troubleshooting

- **No microphone input:** change `MIC_DEVICE_INDEX` in `core/listener.py` to your input device’s index.
- **CUDA error:** set `WHISPER_DEVICE = "cpu"` and `WHISPER_COMPUTE = "int8"` in `core/listener.py`.
- **Piper not found:** correct `PIPER_EXECUTABLE` in `core/speaker.py`.
- **YouTube playback fails:** confirm that VLC is installed and `yt-dlp` is on `PATH`.
- **Groq key error:** verify that `.env` contains a valid `GROQ_API_KEY`.
