"""Local SQLite storage for Altair conversations (stdlib only)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


class ChatHistoryStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.name == "posix":
            os.chmod(os.path.dirname(path), 0o700)
        with closing(self._connect()) as db:
            with db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, updated_at TEXT NOT NULL,
                        model TEXT NOT NULL, reasoning_effort TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                        position INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                        created_at TEXT NOT NULL, model TEXT NOT NULL, reasoning_effort TEXT NOT NULL,
                        FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                        UNIQUE(conversation_id, position)
                    );
                """)
        if os.name == "posix":
            os.chmod(path, 0o600)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def save(self, history: dict, model: str, effort: str):
        conversation_id = str(history["id"])
        title = str(history.get("title") or "Altair chat")
        updated = str(history.get("updated_at") or datetime.now(timezone.utc).isoformat())
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    "INSERT INTO conversations VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at, model=excluded.model, reasoning_effort=excluded.reasoning_effort",
                    (conversation_id, title, updated, model, effort),
                )
                db.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
                db.executemany(
                    "INSERT INTO messages(conversation_id, position, role, content, created_at, model, reasoning_effort) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [(conversation_id, i, str(m.get("role", "")), str(m.get("content", "")), str(m.get("created_at") or updated), model, effort)
                     for i, m in enumerate(history.get("messages", []))],
                )
        if os.name == "posix":
            os.chmod(self.path, 0o600)

    def load(self, conversation_id: str):
        with closing(self._connect()) as db:
            conversation = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if not conversation:
                return None
            messages = db.execute(
                "SELECT role, content, created_at, model, reasoning_effort FROM messages WHERE conversation_id=? ORDER BY position",
                (conversation_id,),
            ).fetchall()
        return {
            "id": conversation["id"], "title": conversation["title"],
            "updated_at": conversation["updated_at"], "model": conversation["model"],
            "reasoning_effort": conversation["reasoning_effort"],
            "messages": [dict(row) for row in messages],
        }

    def list(self):
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT id, title, updated_at, model, reasoning_effort FROM conversations ORDER BY updated_at DESC"
            )]
