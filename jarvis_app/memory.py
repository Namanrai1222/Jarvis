from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    tool_trace TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS agent_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def log_interaction(self, user_text: str, assistant_text: str, tool_trace: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO interactions (user_text, assistant_text, tool_trace) VALUES (?, ?, ?)",
                (user_text, assistant_text, tool_trace),
            )

    def save_fact(self, key: str, value: str, source: str = "manual") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM facts WHERE key = ?", (key,))
            conn.execute(
                "INSERT INTO facts (key, value, source) VALUES (?, ?, ?)",
                (key, value, source),
            )

    def list_facts(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, source, updated_at FROM facts ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_task(self, title: str, details: str = "") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, details) VALUES (?, ?)",
                (title, details),
            )
            return int(cur.lastrowid)

    def complete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET status = 'done', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (task_id,),
            )
            return cur.rowcount > 0

    def list_tasks(self, status: str | None = None) -> list[dict]:
        query = "SELECT id, title, details, status, created_at, updated_at FROM tasks"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def add_document(self, path: str, title: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (path, title, content) VALUES (?, ?, ?)",
                (path, title, content),
            )

    def add_activity(
        self,
        kind: str,
        title: str,
        details: str,
        source: str = "agent",
        metadata: dict | None = None,
    ) -> int:
        payload = json.dumps(metadata or {}, ensure_ascii=True)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO activities (kind, title, details, source, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (kind, title, details, source, payload),
            )
            return int(cur.lastrowid)

    def recent_activities(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, kind, title, details, source, metadata
                FROM activities
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results = [dict(row) for row in rows]
        for item in results:
            item["metadata"] = json.loads(item["metadata"] or "{}")
        return results

    def search_activities(self, query: str, limit: int = 8) -> list[dict]:
        needle = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, kind, title, details, source, metadata
                FROM activities
                WHERE title LIKE ? OR details LIKE ? OR kind LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, needle, limit),
            ).fetchall()
        results = [dict(row) for row in rows]
        for item in results:
            item["metadata"] = json.loads(item["metadata"] or "{}")
        return results

    def search(self, query: str, limit: int = 5) -> list[dict]:
        needle = f"%{query}%"
        with self._connect() as conn:
            doc_rows = conn.execute(
                """
                SELECT 'document' AS kind, title AS label, path AS extra, content AS snippet
                FROM documents
                WHERE content LIKE ? OR title LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, limit),
            ).fetchall()
            fact_rows = conn.execute(
                """
                SELECT 'fact' AS kind, key AS label, source AS extra, value AS snippet
                FROM facts
                WHERE key LIKE ? OR value LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, limit),
            ).fetchall()
            interaction_rows = conn.execute(
                """
                SELECT 'interaction' AS kind, created_at AS label, '' AS extra, assistant_text AS snippet
                FROM interactions
                WHERE user_text LIKE ? OR assistant_text LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, limit),
            ).fetchall()
            activity_rows = conn.execute(
                """
                SELECT 'activity' AS kind, title AS label, created_at AS extra, details AS snippet
                FROM activities
                WHERE title LIKE ? OR details LIKE ? OR kind LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, needle, limit),
            ).fetchall()
        rows = list(doc_rows) + list(fact_rows) + list(interaction_rows)
        rows += list(activity_rows)
        return [dict(row) for row in rows[:limit]]

    def dashboard_state(self) -> dict:
        return {
            "tasks": self.list_tasks()[:8],
            "facts": self.list_facts()[:8],
            "activities": self.recent_activities(8),
        }

    def set_state(self, key: str, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=True)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_state (key, value) VALUES (?, ?)",
                (key, payload),
            )

    def get_state(self, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM agent_state WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return None

    def clear_state(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM agent_state WHERE key = ?", (key,))
