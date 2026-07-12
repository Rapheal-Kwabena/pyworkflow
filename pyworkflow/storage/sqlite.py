"""SQLite-based storage backend, for queryable history and state checkpoints."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from pyworkflow.exceptions import StorageError
from pyworkflow.storage.database import StorageBackend

import os

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    name TEXT PRIMARY KEY,
    definition TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name TEXT NOT NULL,
    report TEXT NOT NULL,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_workflow_name ON runs(workflow_name);
"""


class SQLiteStorage(StorageBackend):
    """Storage backend backed by a SQLite database."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = (
                Path(os.environ.get("HOME", os.path.expanduser("~")))
                / ".pyworkflow"
                / "pyworkflow.db"
            )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_workflow(self, workflow_dict: dict) -> None:
        name = workflow_dict.get("name")
        if not name:
            raise StorageError("workflow_dict must contain a 'name' key")
        try:
            self._conn.execute(
                "INSERT INTO workflows(name, definition, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET definition=excluded.definition, "
                "updated_at=excluded.updated_at",
                (name, json.dumps(workflow_dict, default=str), time.time()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to save workflow '{name}': {exc}") from exc

    def save_run(self, workflow_name: str, report_dict: dict) -> None:
        try:
            self._conn.execute(
                "INSERT INTO runs(workflow_name, report, timestamp) VALUES (?, ?, ?)",
                (workflow_name, json.dumps(report_dict, default=str), time.time()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(
                f"Failed to save run history for '{workflow_name}': {exc}"
            ) from exc

    def get_workflow(self, name: str) -> Optional[dict]:
        cur = self._conn.execute(
            "SELECT definition FROM workflows WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def list_workflows(self) -> list[str]:
        cur = self._conn.execute("SELECT name FROM workflows ORDER BY name")
        return [r[0] for r in cur.fetchall()]

    def get_history(self, workflow_name: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT report, timestamp FROM runs WHERE workflow_name = ? ORDER BY timestamp ASC",
            (workflow_name,),
        )
        results = []
        for report_json, ts in cur.fetchall():
            record = json.loads(report_json)
            record["timestamp"] = ts
            results.append(record)
        return results

    def delete_workflow(self, name: str) -> None:
        self._conn.execute("DELETE FROM workflows WHERE name = ?", (name,))
        self._conn.execute("DELETE FROM runs WHERE workflow_name = ?", (name,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
