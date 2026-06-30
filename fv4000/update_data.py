#!/usr/bin/env python3
"""
update_data.py — Update fv4000/data.json from raw CSV exports.

Auto-detects all CSV files under fv4000/raw/ and classifies each as either
'ratio' (% of nominal power) or 'abs' (absolute detector counts) based on
the filename. Merges new data into fv4000/data.json, preserving existing
sessions that are not in the new files.

Granularity: per MEASUREMENT SESSION (not daily mean). Within each file the
readings are sorted by timestamp and split into sessions wherever the gap
between consecutive readings exceeds SESSION_GAP_MINUTES. For each session,
each laser line is summarised by the MEDIAN of that session's non-zero
readings. Sessions are keyed by their start timestamp ('YYYY-MM-DDTHH:MM:SS'),
so a day with two separate power checks produces two points.

Usage:
    python update_data.py                # process everything under raw/
    python update_data.py --dry-run      # show what would change, don't write
    python update_data.py --verbose      # show per-file details

Filename classification:
    - contains 'ratio' (case-insensitive) -> ratio mode
    - contains 'abs' (case-insensitive)   -> abs mode
    - otherwise: skipped with a warning

CSV format expected (from FV4000 software, both Power check + Power correction
checked, ratio or absolute):
    Date,405,445,488,561,594,640,685,730,785
    YYYY/MM/DD HH:MM:SS,<vals>...

Zeros are treated as 'laser off' and excluded from the session median.

This script uses paths relative to itself, so it works regardless of where
the ZMB-Instruments folder is located on disk.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# All paths are relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "raw"
DATA_JSON = SCRIPT_DIR / "data.json"

LASERS = ["405", "445", "488", "561", "594", "640", "685", "730", "785"]

# A new measurement session starts when the gap between two consecutive
# readings exceeds this many minutes. Tune here to split checks more/less.
SESSION_GAP_MINUTES = 30


def classify_filename(path: Path) -> Optional[str]:
    """Return 'ratio', 'abs', or None based on filename."""
    name = path.name.lower()
    has_ratio = "ratio" in name
    has_abs = "abs" in name
    if has_ratio and not has_abs:
        return "ratio"
    if has_abs and not has_ratio:
        return "abs"
    return None


def parse_dt(raw: str) -> Optional[datetime]:
    """Parse a 'YYYY/MM/DD HH:MM:SS' (or similar) string into a datetime.

    Falls back to a date-only parse (time set to 00:00:00) if no time is present.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    date_part = raw.split(" ")[0]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_part, fmt)
        except ValueError:
            continue
    return None


def read_rows(path: Path) -> list[tuple[datetime, dict[str, float]]]:
    """Read one CSV; return [(datetime, {laser: value}), ...] for usable rows.

    Zero/blank values are skipped (laser off / not measured). No aggregation
    here — sessionising happens once, on the pooled readings of a whole mode,
    so that overlapping cumulative exports don't create boundary-split sessions.
    """
    rows: list[tuple[datetime, dict[str, float]]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_dt(row.get("Date", "") or row.get("date", ""))
            if dt is None:
                continue
            vals: dict[str, float] = {}
            for laser in LASERS:
                raw_val = (row.get(laser) or "").strip()
                if not raw_val:
                    continue
                try:
                    v = float(raw_val)
                except ValueError:
                    continue
                if v <= 0:  # laser off -> skip
                    continue
                vals[laser] = v
            if vals:
                rows.append((dt, vals))
    return rows


def sessionize(rows: list[tuple[datetime, dict[str, float]]],
               verbose: bool = False) -> dict[str, dict[str, Optional[float]]]:
    """Pool readings -> per-session median per laser.

    Readings are de-duplicated by exact timestamp (merging laser columns),
    sorted, then split into sessions wherever the gap between consecutive
    readings exceeds SESSION_GAP_MINUTES. Each session is keyed by its start
    timestamp (ISO 'YYYY-MM-DDTHH:MM:SS') and summarised by the per-laser median.
    """
    # de-dupe identical timestamps across (possibly overlapping) files
    by_dt: dict[datetime, dict[str, float]] = {}
    for dt, vals in rows:
        by_dt.setdefault(dt, {}).update(vals)

    ordered = sorted(by_dt.items())  # [(datetime, {laser: value}), ...]
    gap = timedelta(minutes=SESSION_GAP_MINUTES)
    sessions: list[list[tuple[datetime, dict[str, float]]]] = []
    for dt, vals in ordered:
        if not sessions or (dt - sessions[-1][-1][0]) > gap:
            sessions.append([(dt, vals)])
        else:
            sessions[-1].append((dt, vals))

    out: dict[str, dict[str, Optional[float]]] = {}
    for sess in sessions:
        start_key = sess[0][0].strftime("%Y-%m-%dT%H:%M:%S")
        per_laser: dict[str, list[float]] = {laser: [] for laser in LASERS}
        for _dt, vals in sess:
            for laser, v in vals.items():
                per_laser[laser].append(v)
        out[start_key] = {
            laser: (round(statistics.median(per_laser[laser]), 1) if per_laser[laser] else None)
            for laser in LASERS
        }

    if verbose and out:
        keys = sorted(out)
        print(f"    -> {len(out)} session(s) ({keys[0]} ... {keys[-1]})")
    return out


def merge(existing: dict, incoming: dict) -> tuple[dict, int, int]:
    """Merge incoming sessions into existing. Returns (merged, added, updated)."""
    merged = {d: dict(v) for d, v in existing.items()}
    added = updated = 0
    for key, vals in incoming.items():
        if key not in merged:
            merged[key] = {}
            added += 1
        else:
            updated += 1
        for laser in LASERS:
            if vals.get(laser) is not None:
                merged[key][laser] = vals[laser]
    # Sort by key (ISO timestamps sort chronologically as strings)
    return {d: merged[d] for d in sorted(merged)}, added, updated


def load_existing() -> dict:
    if not DATA_JSON.exists():
        return {"ratio": {}, "abs": {}, "updated": None}
    with DATA_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("ratio", {})
    data.setdefault("abs", {})
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="show what would change, don't write")
    parser.add_argument("--verbose", action="store_true", help="show per-file details")
    parser.add_argument("--rebuild", action="store_true",
                        help="ignore existing data.json and rebuild from raw/ only "
                             "(use when migrating granularity or when raw/ is cumulative)")
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"No raw/ folder found at {RAW_DIR}")
        print("Create it and place CSV exports inside (any nested structure works).")
        return 1

    csv_files = sorted(RAW_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"No CSV files found under {RAW_DIR} — nothing to process.")
        return 2

    print(f"Found {len(csv_files)} CSV file(s) under raw/\n")

    by_mode: dict[str, list[Path]] = {"ratio": [], "abs": []}
    for path in csv_files:
        mode = classify_filename(path)
        rel = path.relative_to(SCRIPT_DIR)
        if mode is None:
            print(f"  ?  {rel}  (skipped - filename must contain 'ratio' or 'abs')")
            continue
        by_mode[mode].append(path)
        print(f"  {mode:5s}  {rel}")
    print()

    if args.rebuild:
        data = {"ratio": {}, "abs": {}, "updated": None}
        print("[rebuild] Ignoring existing data.json; rebuilding from raw/ only.\n")
    else:
        data = load_existing()
    total_added = total_updated = 0

    for mode, files in by_mode.items():
        if not files:
            continue
        print(f"Processing {mode} files ({len(files)})...")
        pooled: list[tuple[datetime, dict[str, float]]] = []
        for path in files:
            if args.verbose:
                print(f"  - {path.relative_to(SCRIPT_DIR)}")
            pooled.extend(read_rows(path))
        combined = sessionize(pooled, verbose=args.verbose)
        merged, added, updated = merge(data[mode], combined)
        data[mode] = merged
        total_added += added
        total_updated += updated
        print(f"  -> {added} new session(s), {updated} updated session(s)")
        print()

    data["updated"] = datetime.now().strftime("%Y-%m-%d")

    print("-" * 50)
    print(f"Summary: {total_added} session(s) added, {total_updated} updated")
    print(f"data.json now contains {len(data['ratio'])} ratio session(s), {len(data['abs'])} abs session(s)")

    if total_added == 0:
        print("No new sessions — nothing to publish.")
        return 2

    if args.dry_run:
        print("\n[dry-run] No changes written.")
        return 0

    with DATA_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
    print(f"\nWritten to {DATA_JSON.relative_to(SCRIPT_DIR.parent)}")

    latest_date = None
    for mode in ("ratio", "abs"):
        keys = sorted(data.get(mode, {}).keys())
        if keys:
            candidate = keys[-1][:10]  # YYYY-MM-DD from ISO timestamp
            if latest_date is None or candidate > latest_date:
                latest_date = candidate
    date_str = latest_date or data.get("updated", "YYYY-MM-DD")
    (SCRIPT_DIR / ".qc_last_date").write_text(date_str, encoding="utf-8")
    print("\nNext step - commit and push:")
    print("  git add fv4000/data.json")
    print(f'  git commit -m "Update FV4000 data - {date_str}"')
    print("  git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
