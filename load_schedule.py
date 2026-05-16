"""
Load schedule.yaml into schedule.db (SQLite).

Run with: python load_schedule.py

Idempotent: rerunning it wipes and recreates the tables, so it's safe to
re-run any time you edit schedule.yaml.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

DB_PATH = Path(__file__).parent / "schedule.db"
YAML_PATH = Path(__file__).parent / "schedule.yaml"

# Schema: two tables, one for weekly recurring class meetings, one for finals.
# We keep the weekly view dead simple — one row per (course, type, day).
SCHEMA = """
DROP TABLE IF EXISTS meetings;
DROP TABLE IF EXISTS finals;
DROP TABLE IF EXISTS meta;

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE meetings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course    TEXT    NOT NULL,
    section   TEXT    NOT NULL,
    type      TEXT    NOT NULL,        -- Lec, Dis, Lab
    day       TEXT    NOT NULL,        -- M, T, W, Th, F
    start     TEXT    NOT NULL,        -- HH:MM, 24h
    end       TEXT    NOT NULL,        -- HH:MM, 24h
    location  TEXT    NOT NULL
);

CREATE INDEX idx_meetings_day ON meetings(day);
CREATE INDEX idx_meetings_course ON meetings(course);

CREATE TABLE finals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course    TEXT    NOT NULL,
    date      TEXT    NOT NULL,        -- YYYY-MM-DD
    time      TEXT    NOT NULL,        -- HH:MM, 24h
    location  TEXT    NOT NULL
);

CREATE INDEX idx_finals_date ON finals(date);
"""


def main() -> None:
    if not YAML_PATH.exists():
        raise SystemExit(f"schedule.yaml not found at {YAML_PATH}")

    with open(YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Recreate tables from scratch — simplest correct strategy for a 200-row
    # personal dataset. For a real production app you'd diff and upsert.
    cur.executescript(SCHEMA)

    # Metadata
    for key in ("semester", "timezone", "term_start", "term_end"):
        if key in data:
            cur.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                (key, str(data[key])),
            )

    # Weekly meetings — one row per day for each meeting pattern.
    # If a class meets MWF, that becomes three rows. Simpler than storing a
    # bitmask, and queries like "what's on Monday" become trivial.
    meeting_count = 0
    for cls in data.get("classes", []):
        for day in cls["days"]:
            cur.execute(
                """
                INSERT INTO meetings
                    (course, section, type, day, start, end, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cls["course"],
                    cls["section"],
                    cls["type"],
                    day,
                    cls["start"],
                    cls["end"],
                    cls["location"],
                ),
            )
            meeting_count += 1

    # Finals
    final_count = 0
    for final in data.get("finals", []):
        cur.execute(
            """
            INSERT INTO finals (course, date, time, location)
            VALUES (?, ?, ?, ?)
            """,
            (
                final["course"],
                str(final["date"]),
                final["time"],
                final["location"],
            ),
        )
        final_count += 1

    conn.commit()
    conn.close()

    print(f"Loaded {meeting_count} weekly meetings and {final_count} finals.")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
