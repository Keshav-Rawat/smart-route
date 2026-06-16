"""
SmartRoute — SQLite Persistence Layer
=======================================
Provides persistent storage for traffic readings and intersection state.
Uses Python's built-in sqlite3 — no extra dependencies required.

The database file is created at backend/smartroute.db automatically.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Any

DB_PATH = os.environ.get(
    "SMARTROUTE_DB",
    os.path.join(os.path.dirname(__file__), "smartroute.db")
)
HISTORY_LIMIT = 500  # max rows per intersection kept in DB


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent read/write
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called once at startup."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS intersections (
                intersection_id  TEXT PRIMARY KEY,
                vehicle_count    INTEGER DEFAULT 0,
                signal_state     TEXT DEFAULT 'GREEN',
                algorithm        TEXT DEFAULT 'adaptive',
                lanes            TEXT DEFAULT '{}',
                unique_total     INTEGER DEFAULT 0,
                last_updated     TEXT
            );

            CREATE TABLE IF NOT EXISTS traffic_readings (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                intersection_id  TEXT NOT NULL,
                vehicle_count    INTEGER NOT NULL,
                signal_state     TEXT NOT NULL,
                lanes            TEXT DEFAULT '{}',
                timestamp        TEXT NOT NULL,
                FOREIGN KEY (intersection_id) REFERENCES intersections(intersection_id)
            );

            CREATE INDEX IF NOT EXISTS idx_readings_intersection
                ON traffic_readings(intersection_id, timestamp DESC);
        """)

    # Seed default intersection if not present
    upsert_intersection_state("intersection_1", 0, "GREEN", {})
    conn.close()
    print(f"✅ Database ready: {DB_PATH}")


# ── Intersection State (current snapshot) ────────────────────────

def upsert_intersection_state(
    intersection_id: str,
    vehicle_count: int,
    signal_state: str,
    lanes: dict,
    algorithm: str = "adaptive",
    unique_total: int = 0,
) -> None:
    """Insert or update the current state for an intersection."""
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO intersections
                (intersection_id, vehicle_count, signal_state, algorithm,
                 lanes, unique_total, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(intersection_id) DO UPDATE SET
                vehicle_count = excluded.vehicle_count,
                signal_state  = excluded.signal_state,
                algorithm     = excluded.algorithm,
                lanes         = excluded.lanes,
                unique_total  = excluded.unique_total,
                last_updated  = excluded.last_updated
        """, (
            intersection_id,
            vehicle_count,
            signal_state,
            algorithm,
            json.dumps(lanes),
            unique_total,
            datetime.now().isoformat(),
        ))
    conn.close()


def get_intersection_state(intersection_id: str) -> dict | None:
    """Return current state of an intersection, or None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM intersections WHERE intersection_id = ?",
        (intersection_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "intersection_id": row["intersection_id"],
        "vehicle_count":   row["vehicle_count"],
        "signal_state":    row["signal_state"],
        "algorithm":       row["algorithm"],
        "lanes":           json.loads(row["lanes"] or "{}"),
        "unique_total":    row["unique_total"],
        "last_updated":    row["last_updated"],
    }


def list_all_intersections() -> list[dict]:
    """Return all known intersections and their current state."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM intersections").fetchall()
    conn.close()
    return [
        {
            "intersection_id": r["intersection_id"],
            "vehicle_count":   r["vehicle_count"],
            "signal_state":    r["signal_state"],
            "last_updated":    r["last_updated"],
        }
        for r in rows
    ]


# ── Traffic Readings (history) ────────────────────────────────────

def insert_reading(
    intersection_id: str,
    vehicle_count: int,
    signal_state: str,
    lanes: dict,
) -> None:
    """Append a new traffic reading and prune old rows."""
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO traffic_readings
                (intersection_id, vehicle_count, signal_state, lanes, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            intersection_id,
            vehicle_count,
            signal_state,
            json.dumps(lanes),
            datetime.now().isoformat(),
        ))

        # Keep only the most recent HISTORY_LIMIT rows per intersection
        conn.execute("""
            DELETE FROM traffic_readings
            WHERE intersection_id = ?
              AND id NOT IN (
                  SELECT id FROM traffic_readings
                  WHERE intersection_id = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
        """, (intersection_id, intersection_id, HISTORY_LIMIT))
    conn.close()


def get_history(intersection_id: str, limit: int = 100) -> list[dict]:
    """Return the last `limit` readings for an intersection."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT vehicle_count, signal_state, lanes, timestamp
        FROM   traffic_readings
        WHERE  intersection_id = ?
        ORDER  BY id DESC
        LIMIT  ?
    """, (intersection_id, limit)).fetchall()
    conn.close()

    # Return chronological order (oldest first)
    return [
        {
            "timestamp":     r["timestamp"],
            "count":         r["vehicle_count"],
            "signal":        r["signal_state"],
            "lanes":         json.loads(r["lanes"] or "{}"),
        }
        for r in reversed(rows)
    ]


def reset_intersection(intersection_id: str) -> None:
    """Clear all readings and reset state for an intersection."""
    conn = get_connection()
    with conn:
        conn.execute(
            "DELETE FROM traffic_readings WHERE intersection_id = ?",
            (intersection_id,)
        )
        conn.execute("""
            UPDATE intersections
            SET vehicle_count = 0,
                signal_state  = 'GREEN',
                lanes         = '{}',
                unique_total  = 0,
                last_updated  = ?
            WHERE intersection_id = ?
        """, (datetime.now().isoformat(), intersection_id))
    conn.close()
