#!/usr/bin/env python3
"""
stamp_kb_maintenance.py — Write the measurement date into the KB maintenance config.

Called by update_instruments_QC.bat after a successful QC run.
Reads the latest session date from data.json, then writes it to the KB config
under <instrument>_last_measured — only when the new date is newer than the
existing value (never stamps a no-op run).

Usage:
    python stamp_kb_maintenance.py <instrument> <data_json> <kb_config>

Example:
    python stamp_kb_maintenance.py fv4000 fv4000\data.json ^
        Z:\home\j.delgado\ZMB\data\curated\_maintenance_config.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(f"Usage: {Path(sys.argv[0]).name} <instrument> <data_json> <kb_config>")
        return 1

    instrument = sys.argv[1]
    data_json = Path(sys.argv[2])
    kb_config = Path(sys.argv[3])
    config_key = f"{instrument}_last_measured"

    if not data_json.exists():
        print(f"[stamp] ERROR: {data_json} not found")
        return 1
    if not kb_config.exists():
        print(f"[stamp] ERROR: {kb_config} not found")
        return 1

    with data_json.open("r", encoding="utf-8") as f:
        data = json.load(f)

    latest_date: str | None = None
    for mode in ("ratio", "abs"):
        keys = sorted(data.get(mode, {}).keys())
        if keys:
            candidate = keys[-1][:10]  # YYYY-MM-DD from ISO timestamp
            if latest_date is None or candidate > latest_date:
                latest_date = candidate

    if not latest_date:
        print(f"[stamp] No session data found in {data_json} — nothing to stamp.")
        return 0

    with kb_config.open("r", encoding="utf-8") as f:
        config = json.load(f)

    existing = config.get(config_key, "")
    if existing and existing >= latest_date:
        print(f"[stamp] {config_key} already up to date ({existing}) — no change.")
        return 0

    config[config_key] = latest_date
    with kb_config.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"[stamp] {config_key}: {existing or '<empty>'} -> {latest_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
