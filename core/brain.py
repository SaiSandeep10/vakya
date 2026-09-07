"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 3 Update | core/brain.py

Changes from Week 2:
  - Accepts optional memory_context string
  - Injects memory context into every prompt before sending to Groq
"""

import os
from groq import Groq
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

load_dotenv()

GROQ_MODEL    = "allam-2-7b"
MAX_TOKENS    = 300
TEMPERATURE   = 0.7
MAX_HISTORY   = 10

SYSTEM_PROMPT = """
You are V.A.K.Y.A — Voice Activated Knowledge Yantric Agent.
You are a personal AI assistant running entirely on the user's local machine.
You were built by Sai Sandeep.

Your personality:
- Intelligent, precise, and helpful
- Concise — you are a VOICE assistant, keep responses short and natural
- Never use bullet points, markdown, or formatting in responses
- Speak in plain conversational sentences only
- If you don't know something, say so clearly

If a [ VAKYA Memory Context ] block is provided, use it to personalise your response.
The memory context contains facts the user has told you in previous sessions.

Always respond as if you are being heard, not read.
Never say you are an AI made by Meta or any other company.
You are V.A.K.Y.A, built by Sai Sandeep.
""".strip()


# ──────────────────────────────────────────────
# BRAIN CLASS
# ──────────────────────────────────────────────

class Brain:
    """
    Intelligence layer of VAKYA.
    Now memory-aware — injects context from memory.py into every prompt.
    """

    def __init__(self):
        print("[VAKYA] Initialising Brain...")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "[VAKYA Brain] GROQ_API_KEY not found in .env file.\n"
                "Create a .env file with: GROQ_API_KEY=gsk_yourkey"
            )

        self._client  = Groq(api_key=api_key)
        self._history = []

        print(f"[VAKYA] Brain ready. Model: {GROQ_MODEL}")

    # ── PUBLIC API ──────────────────────────────

    def think(self, user_input: str, memory_context: str = "") -> str:
        """
        Send user input to Groq and return VAKYA's response.

        memory_context: optional string from memory.build_context()
                        injected before the user message if provided.
        """
        if not user_input or not user_input.strip():
            return "I didn't catch that. Could you repeat?"

        # Prepend memory context to user message if available
        user_message = user_input.strip()
        if memory_context and memory_context.strip():
            user_message = f"{memory_context}\nUser query: {user_message}"

        self._history.append({"role": "user", "content": user_message})

        # Trim history to avoid token overflow
        if len(self._history) > MAX_HISTORY * 2:
            self._history = self._history[-(MAX_HISTORY * 2):]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history

        try:
            print("[VAKYA] Thinking...")

            response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )

            reply = response.choices[0].message.content.strip()

            self._history.append({"role": "assistant", "content": reply})

            print(f"[VAKYA] Response: \"{reply[:80]}{'...' if len(reply) > 80 else ''}\"")
            return reply

        except Exception as e:
            print(f"[VAKYA Brain] ERROR: {e}")
            return "I ran into an error. Please check your internet connection and try again."

    def reset(self):
        """Clear conversation history."""
        self._history = []
        print("[VAKYA] Conversation history cleared.")


# ──────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    brain = Brain()
    print("\n[TEST] VAKYA Brain — type questions, 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "quit":
                break
            if user_input.lower() == "reset":
                brain.reset()
                continue
            response = brain.think(user_input)
            print(f"\nVAKYA: {response}\n")
        except KeyboardInterrupt:
            break