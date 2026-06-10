# umd-schedule-mcp

Python MCP server that exposes my UMD class schedule to Claude via SQLite.

## Overview

Reads a class schedule from `schedule.yaml`, loads it into a local SQLite database (`schedule.db`), and serves it over the Model Context Protocol. Any MCP client (Claude Code, MCP Inspector, etc.) can then query the schedule with natural language.

## Tools

| Tool | Description |
|------|-------------|
| `get_classes_today` | All meetings scheduled for today, sorted by start time. Empty on weekends/no classes. |
| `get_next_class` | The next meeting from right now. Counts a class in session as "next"; rolls forward to the next day with classes if nothing's left today. |
| `get_classes_for_day` | All meetings for a given day. Accepts `M`, `T`, `W`, `Th`, `F` or full names like `Monday` (case-insensitive). |
| `find_class` | All meetings for a course by code or substring (e.g. `CMSC 131`, `chem`). Case-insensitive. |

## Requirements

- Python 3.9+ (uses `zoneinfo`)
- `mcp>=1.0.0`, `pyyaml>=6.0`

## Setup

```bash
git clone https://github.com/poplores/umd-schedule-mcp.git
cd umd-schedule-mcp

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Loading the schedule

Edit `schedule.yaml` with your courses, then build the database:

```bash
python load_schedule.py
```

This creates `schedule.db`. Re-run it whenever you change `schedule.yaml`.

## Running the server

```bash
python server.py
```

The server uses stdio transport by default.

## Connecting to Claude Code

```bash
claude mcp add umd-schedule -- python /absolute/path/to/server.py
```

Then ask things like "What classes do I have today?" or "When does my chem class meet?"

## Files

| File | Purpose |
|------|---------|
| `schedule.yaml` | Source of truth for course data |
| `load_schedule.py` | Loads YAML into SQLite (`schedule.db`) |
| `server.py` | MCP server exposing the four schedule tools |
| `requirements.txt` | Python dependencies |
