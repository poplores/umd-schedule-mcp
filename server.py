"""
UMD schedule MCP server.

Exposes four tools to any MCP client (Claude Code, MCP Inspector, etc.):
  - get_classes_today
  - get_next_class
  - get_classes_for_day
  - find_class

Run directly with: python server.py
Or via Claude Code: claude mcp add umd-schedule -- python /path/to/server.py
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, date, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "schedule.db"
DAY_CODES = ["M", "T", "W", "Th", "F", "Sa", "Su"]  # Monday=0 in Python's weekday()

mcp = FastMCP("umd-schedule")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"schedule.db not found at {DB_PATH}. "
            "Run `python load_schedule.py` first to create it."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _timezone() -> ZoneInfo:
    """Read the timezone from the meta table, default to America/New_York."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'timezone'"
        ).fetchone()
        return ZoneInfo(row["value"] if row else "America/New_York")
    finally:
        conn.close()


def _today_code() -> str:
    """Day code for today, in the configured timezone."""
    now = datetime.now(_timezone())
    return DAY_CODES[now.weekday()]


def _format_meeting(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "course": row["course"],
        "section": row["section"],
        "type": row["type"],
        "day": row["day"],
        "start": row["start"],
        "end": row["end"],
        "location": row["location"],
    }


# ----------------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------------


@mcp.tool()
def get_classes_today() -> list[dict[str, Any]]:
    """
    Get all class meetings scheduled for today, sorted by start time.

    Returns an empty list if today is a weekend or there are no classes.
    """
    day = _today_code()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT course, section, type, day, start, end, location
            FROM meetings
            WHERE day = ?
            ORDER BY start
            """,
            (day,),
        ).fetchall()
    finally:
        conn.close()

    return [_format_meeting(r) for r in rows]


@mcp.tool()
def get_next_class() -> dict[str, Any] | None:
    """
    Get the next class meeting starting from right now.

    If a class is currently in session, it counts as 'next' (the start time
    today is in the past, but you're still in it). If nothing is scheduled
    later today, it rolls forward to the next day with classes.

    Returns None if there are no classes anywhere in the schedule.
    """
    tz = _timezone()
    now = datetime.now(tz)
    today_code = DAY_CODES[now.weekday()]
    current_hhmm = now.strftime("%H:%M")

    conn = _connect()
    try:
        # First: anything left today that hasn't ended yet
        row = conn.execute(
            """
            SELECT course, section, type, day, start, end, location
            FROM meetings
            WHERE day = ? AND end > ?
            ORDER BY start
            LIMIT 1
            """,
            (today_code, current_hhmm),
        ).fetchone()

        if row:
            return _format_meeting(row)

        # Otherwise: walk forward through the week until we find a day with classes
        for offset in range(1, 8):
            future_idx = (now.weekday() + offset) % 7
            future_code = DAY_CODES[future_idx]
            row = conn.execute(
                """
                SELECT course, section, type, day, start, end, location
                FROM meetings
                WHERE day = ?
                ORDER BY start
                LIMIT 1
                """,
                (future_code,),
            ).fetchone()
            if row:
                return _format_meeting(row)

        return None
    finally:
        conn.close()


@mcp.tool()
def get_classes_for_day(day: str) -> list[dict[str, Any]]:
    """
    Get all class meetings for a specific day of the week.

    Args:
        day: One of M, T, W, Th, F (Monday through Friday).
             Case-insensitive. Also accepts full names like 'Monday'.

    Returns an empty list if no classes meet on that day.
    """
    # Normalize input
    aliases = {
        "monday": "M", "mon": "M", "m": "M",
        "tuesday": "T", "tue": "T", "tues": "T", "t": "T",
        "wednesday": "W", "wed": "W", "w": "W",
        "thursday": "Th", "thu": "Th", "thur": "Th", "thurs": "Th", "th": "Th",
        "friday": "F", "fri": "F", "f": "F",
    }
    code = aliases.get(day.lower().strip())
    if code is None:
        raise ValueError(
            f"Unknown day: {day!r}. Use M, T, W, Th, or F."
        )

    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT course, section, type, day, start, end, location
            FROM meetings
            WHERE day = ?
            ORDER BY start
            """,
            (code,),
        ).fetchall()
    finally:
        conn.close()

    return [_format_meeting(r) for r in rows]


@mcp.tool()
def find_class(query: str) -> list[dict[str, Any]]:
    """
    Find all meetings for a class by course code or partial match.

    Args:
        query: A course code (e.g. 'CMSC 131') or substring ('CMSC', 'chem').
               Case-insensitive.

    Returns all matching meetings across all days. Useful for "when does my
    chem class meet?" style questions.
    """
    if not query.strip():
        return []

    pattern = f"%{query.strip()}%"
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT course, section, type, day, start, end, location
            FROM meetings
            WHERE course LIKE ? COLLATE NOCASE
            ORDER BY
                CASE day
                    WHEN 'M'  THEN 1
                    WHEN 'T'  THEN 2
                    WHEN 'W'  THEN 3
                    WHEN 'Th' THEN 4
                    WHEN 'F'  THEN 5
                    ELSE 6
                END,
                start
            """,
            (pattern,),
        ).fetchall()
    finally:
        conn.close()

    return [_format_meeting(r) for r in rows]


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    # FastMCP defaults to stdio transport — same as the TypeScript server.
    mcp.run()
