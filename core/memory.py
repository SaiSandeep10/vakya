"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 3 | core/memory.py

Two-tier memory architecture:

  Tier 1 — ChromaDB (semantic / fuzzy recall)
    - Personal facts: name, allergies, preferences
    - Past conversation summaries
    - Music preferences

  Tier 2 — SQLite (structured / exact recall)
    - Reminders with exact timestamps
    - Timers
    - Key-value user facts (fast lookup)

Usage:
    memory = Memory()

    # Store a fact
    memory.remember("I am allergic to peanuts")
    memory.remember("My favourite artist is AR Rahman")

    # Recall relevant facts before sending to brain
    facts = memory.recall("what food should I avoid")
    # returns: ["User is allergic to peanuts"]

    # Reminders
    memory.add_reminder("Call Mum", "2026-05-14 15:00")
    memory.get_due_reminders()   # returns reminders due now
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

BASE_DIR        = Path(__file__).parent.parent
CHROMA_PATH     = BASE_DIR / "data" / "chroma_db"
SQLITE_PATH     = BASE_DIR / "data" / "vakya.db"

COLLECTION_FACTS    = "personal_facts"
COLLECTION_CONVOS   = "conversations"
COLLECTION_MUSIC    = "music_preferences"

MAX_RECALL_RESULTS  = 5      # max facts returned per recall query
MIN_RECALL_SCORE    = 0.4    # relevance threshold (0–1, lower = more results)


# ──────────────────────────────────────────────
# MEMORY CLASS
# ──────────────────────────────────────────────

class Memory:
    """
    Persistent memory for VAKYA across sessions.

    ChromaDB handles semantic (fuzzy) memory.
    SQLite handles structured (exact) memory.
    """

    def __init__(self):
        print("[VAKYA] Initialising Memory...")

        # ── ChromaDB setup ───────────────────────
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)

        self._chroma = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False)
        )

        # Three semantic collections
        self._facts  = self._chroma.get_or_create_collection(COLLECTION_FACTS)
        self._convos = self._chroma.get_or_create_collection(COLLECTION_CONVOS)
        self._music  = self._chroma.get_or_create_collection(COLLECTION_MUSIC)

        # ── SQLite setup ─────────────────────────
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._setup_sqlite()

        print(f"[VAKYA] Memory ready.")
        print(f"[VAKYA]   ChromaDB @ {CHROMA_PATH}")
        print(f"[VAKYA]   SQLite   @ {SQLITE_PATH}")

    # ──────────────────────────────────────────
    # SQLITE SCHEMA
    # ──────────────────────────────────────────

    def _setup_sqlite(self):
        """Create tables if they don't exist."""
        cur = self._db.cursor()

        # Reminders table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT    NOT NULL,
                due_at      TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                done        INTEGER DEFAULT 0
            )
        """)

        # Key-value facts table (fast exact lookup)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        self._db.commit()

    # ──────────────────────────────────────────
    # SEMANTIC MEMORY — ChromaDB
    # ──────────────────────────────────────────

    def remember(self, text: str, category: str = "fact") -> str:
        """
        Store a memory in the appropriate ChromaDB collection.

        category: "fact" | "conversation" | "music"

        Returns the stored memory ID.
        """
        text = text.strip()
        if not text:
            return ""

        collection = self._get_collection(category)
        memory_id  = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        collection.add(
            documents=[text],
            ids=[memory_id],
            metadatas=[{
                "category":   category,
                "created_at": datetime.now().isoformat(),
            }]
        )

        print(f"[VAKYA Memory] Stored ({category}): \"{text[:60]}\"")
        return memory_id

    def recall(self, query: str, category: str = None, n: int = MAX_RECALL_RESULTS) -> list[str]:
        """
        Search semantic memory for facts relevant to the query.

        If category is None, searches all three collections.
        Returns a list of matching memory strings.
        """
        query = query.strip()
        if not query:
            return []

        results = []
        collections = (
            [self._get_collection(category)] if category
            else [self._facts, self._convos, self._music]
        )

        for col in collections:
            if col.count() == 0:
                continue
            try:
                res = col.query(
                    query_texts=[query],
                    n_results=min(n, col.count()),
                    include=["documents", "distances"]
                )
                for doc, dist in zip(res["documents"][0], res["distances"][0]):
                    # ChromaDB distance: lower = more similar
                    # Convert to score: 1 - distance
                    score = 1.0 - dist
                    if score >= MIN_RECALL_SCORE:
                        results.append((score, doc))
            except Exception as e:
                print(f"[VAKYA Memory] Recall error: {e}")

        # Sort by relevance, return top N
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:n]]

    def forget(self, memory_id: str):
        """Delete a specific memory by ID."""
        for col in [self._facts, self._convos, self._music]:
            try:
                col.delete(ids=[memory_id])
            except Exception:
                pass

    def remember_conversation(self, user_text: str, vakya_reply: str):
        """
        Store a conversation summary after each exchange.
        Called by main.py after every successful response.
        """
        summary = f"User said: {user_text} | VAKYA replied: {vakya_reply}"
        self.remember(summary, category="conversation")

    # ──────────────────────────────────────────
    # MUSIC PREFERENCES
    # ──────────────────────────────────────────

    def remember_music(self, preference: str):
        """Store a music preference fact."""
        self.remember(preference, category="music")

    def recall_music(self, query: str = "music preferences") -> list[str]:
        """Recall music preferences relevant to a query."""
        return self.recall(query, category="music")

    # ──────────────────────────────────────────
    # REMINDERS — SQLite
    # ──────────────────────────────────────────

    def add_reminder(self, label: str, due_at: str) -> int:
        """
        Add a reminder.

        due_at format: 'YYYY-MM-DD HH:MM'
        Returns the reminder ID.
        """
        cur = self._db.cursor()
        cur.execute("""
            INSERT INTO reminders (label, due_at, created_at)
            VALUES (?, ?, ?)
        """, (label.strip(), due_at.strip(), datetime.now().isoformat()))
        self._db.commit()
        rid = cur.lastrowid
        print(f"[VAKYA Memory] Reminder set: '{label}' at {due_at} (id={rid})")
        return rid

    def get_due_reminders(self) -> list[dict]:
        """
        Return all reminders that are due now or overdue.
        Marks them as done automatically.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = self._db.cursor()
        cur.execute("""
            SELECT id, label, due_at FROM reminders
            WHERE done = 0 AND due_at <= ?
        """, (now,))
        rows = cur.fetchall()

        due = [{"id": r["id"], "label": r["label"], "due_at": r["due_at"]} for r in rows]

        if due:
            ids = [str(r["id"]) for r in due]
            cur.execute(f"""
                UPDATE reminders SET done = 1
                WHERE id IN ({','.join(ids)})
            """)
            self._db.commit()

        return due

    def list_reminders(self) -> list[dict]:
        """List all pending (not done) reminders."""
        cur = self._db.cursor()
        cur.execute("""
            SELECT id, label, due_at FROM reminders
            WHERE done = 0
            ORDER BY due_at ASC
        """)
        return [{"id": r["id"], "label": r["label"], "due_at": r["due_at"]}
                for r in cur.fetchall()]

    def cancel_reminder(self, reminder_id: int):
        """Cancel a reminder by ID."""
        cur = self._db.cursor()
        cur.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))
        self._db.commit()
        print(f"[VAKYA Memory] Reminder {reminder_id} cancelled.")

    # ──────────────────────────────────────────
    # USER FACTS — SQLite key-value
    # ──────────────────────────────────────────

    def set_fact(self, key: str, value: str):
        """
        Store a structured key-value fact.
        Example: set_fact("name", "Sai Sandeep")
        """
        cur = self._db.cursor()
        cur.execute("""
            INSERT INTO user_facts (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value      = excluded.value,
                updated_at = excluded.updated_at
        """, (key.lower().strip(), value.strip(), datetime.now().isoformat()))
        self._db.commit()
        print(f"[VAKYA Memory] Fact set: {key} = {value}")

    def get_fact(self, key: str) -> str | None:
        """Retrieve a structured fact by key."""
        cur = self._db.cursor()
        cur.execute("SELECT value FROM user_facts WHERE key = ?", (key.lower().strip(),))
        row = cur.fetchone()
        return row["value"] if row else None

    def get_all_facts(self) -> dict:
        """Return all structured key-value facts."""
        cur = self._db.cursor()
        cur.execute("SELECT key, value FROM user_facts")
        return {row["key"]: row["value"] for row in cur.fetchall()}

    # ──────────────────────────────────────────
    # CONTEXT BUILDER — called by brain.py
    # ──────────────────────────────────────────

    def build_context(self, query: str) -> str:
        """
        Build a memory context string to prepend to the LLM prompt.
        Searches all semantic memory for relevant facts.

        Returns empty string if nothing relevant found.
        """
        recalled = self.recall(query)
        facts    = self.get_all_facts()

        lines = []

        if facts:
            lines.append("Known facts about the user:")
            for k, v in facts.items():
                lines.append(f"  - {k}: {v}")

        if recalled:
            lines.append("Relevant memories:")
            for mem in recalled:
                lines.append(f"  - {mem}")

        if not lines:
            return ""

        return "[ VAKYA Memory Context ]\n" + "\n".join(lines) + "\n[ End of Memory Context ]\n"

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _get_collection(self, category: str):
        return {
            "fact":         self._facts,
            "conversation": self._convos,
            "music":        self._music,
        }.get(category, self._facts)

    def stats(self) -> dict:
        """Return memory statistics."""
        cur = self._db.cursor()
        cur.execute("SELECT COUNT(*) as c FROM reminders WHERE done = 0")
        pending_reminders = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM user_facts")
        total_facts = cur.fetchone()["c"]

        return {
            "semantic_facts":        self._facts.count(),
            "semantic_conversations": self._convos.count(),
            "semantic_music":        self._music.count(),
            "structured_facts":      total_facts,
            "pending_reminders":     pending_reminders,
        }

    def close(self):
        """Close SQLite connection."""
        self._db.close()


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python core/memory.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    memory = Memory()

    print("\n── Storing personal facts ──")
    memory.remember("I am allergic to peanuts", category="fact")
    memory.remember("My name is Sai Sandeep", category="fact")
    memory.remember("I prefer dark mode in all apps", category="fact")
    memory.set_fact("name", "Sai Sandeep")
    memory.set_fact("location", "Karnataka, India")

    print("\n── Storing music preferences ──")
    memory.remember_music("My favourite artist is AR Rahman")
    memory.remember_music("I love listening to classical Carnatic music")
    memory.remember_music("My go-to playlist for focus is lo-fi beats")

    print("\n── Storing a conversation ──")
    memory.remember_conversation(
        "What is quantum computing?",
        "Quantum computing uses quantum bits that can be 0 and 1 simultaneously."
    )

    print("\n── Adding a reminder ──")
    memory.add_reminder("Check VAKYA Week 4 progress", "2026-05-14 18:00")

    print("\n── Recalling facts about food ──")
    results = memory.recall("what food should I avoid")
    for r in results:
        print(f"  → {r}")

    print("\n── Recalling music preferences ──")
    results = memory.recall_music("what music do I like")
    for r in results:
        print(f"  → {r}")

    print("\n── Building context for a query ──")
    context = memory.build_context("suggest a recipe for dinner")
    print(context)

    print("\n── Memory stats ──")
    stats = memory.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    memory.close()
    print("\n[TEST] Done.")