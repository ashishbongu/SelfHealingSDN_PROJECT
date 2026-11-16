import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DATA_DIR, DATABASE_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                controller TEXT NOT NULL,
                topology TEXT NOT NULL,
                failure_link TEXT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                summary_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS recovery_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER,
                link TEXT NOT NULL,
                action TEXT NOT NULL,
                detection_ms REAL,
                recovery_ms REAL,
                verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(experiment_id) REFERENCES experiments(id)
            );
            """
        )


def add_event(event_type: str, severity: str, message: str,
              metadata: dict[str, Any] | None = None) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO events
               (event_type, severity, message, created_at, metadata_json)
               VALUES (?, ?, ?, ?, ?)""",
            (event_type, severity, message, utc_now(), json.dumps(metadata or {})),
        )
        return int(cursor.lastrowid)


def list_events(limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "severity": row["severity"],
            "message": row["message"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata_json"]),
        }
        for row in rows
    ]


def create_experiment(controller: str, topology: str, failure_link: str | None) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO experiments
               (controller, topology, failure_link, status, started_at)
               VALUES (?, ?, ?, 'planned', ?)""",
            (controller, topology, failure_link, utc_now()),
        )
        return int(cursor.lastrowid)


def list_experiments(limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "id": row["id"],
            "controller": row["controller"],
            "topology": row["topology"],
            "failure_link": row["failure_link"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "summary": json.loads(row["summary_json"]),
        }
        for row in rows
    ]

