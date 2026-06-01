#!/usr/bin/env python3
"""
update_data.py — Update fv4000/data.json from raw CSV exports.

Auto-detects all CSV files under fv4000/raw/ and classifies each as either
'ratio' (% of nominal power) or 'abs' (absolute detector counts) based on
the filename. Merges new data into fv4000/data.json, preserving existing
days that are not in the new files.

Usage:
    python update_data.py                # process everything under raw/
    python update_data.py --dry-run      # show what would change, don't write
    python update_data.py --verbose      # show per-file details

Filename classification:
    - contains 'ratio' (case-insensitive) → ratio mode
    - contains 'abs' (case-insensitive)   → abs mode
    - otherwise: skipped with a warning

CSV format expected (from FV4000 software, both Power check + Power correction
checked, ratio or absolute):
    Date,405,445,488,561,594,640,685,730,785
    YYYY/MM/DD HH:MM:SS,<vals>...

Zeros are treated as 'laser off' and excluded from the daily mean.

This script uses paths relative to itself, so it works regardless of where
the ZMB-Instruments folder is located on disk.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# All paths are relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "raw"
DATA_JSON = SCRIPT_DIR / "data.json"

LASERS = ["405", "445", "488", "561", "594", "640", "685", "730", "785"]


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


def parse_date(raw: str) -> Optional[str]:
    """Parse a date string into YYYY-MM-DD format."""
    raw = raw.strip()
    if not raw:
        return None
    date_part = raw.split(" ")[0]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_part, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def aggregate_csv(path: Path, verbose: bool = False) -> dict[str, dict[str, float]]:
    """Read a CSV and return daily means per laser line.

    Zero values are excluded (treated as laser off).
    """
    sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            day = parse_date(row.get("Date", "") or row.get("date", ""))
            if not day:
                continue
            for laser in LASERS:
                raw_val = (row.get(laser) or "").strip()
                if not raw_val:
                    continue
                try:
                    v = float(raw_val)
                except ValueError:
                    continue
                if v <= 0:  # laser off → skip
                    continue
                sums[day][laser] += v
                counts[day][laser] += 1

    out: dict[str, dict[str, float]] = {}
    for day in sorted(sums.keys()):
        out[day] = {}
        for laser in LASERS:
            c = counts[day].get(laser, 0)
            out[day][laser] = round(sums[day][laser] / c, 1) if c > 0 else None

    if verbose:
        print(f"    → {len(out)} day(s) extracted ({min(out)} … {max(out)})")
    return out


def merge(existing: dict, incoming: dict) -> tuple[dict, int, int]:
    """Merge incoming data into existing. Returns (merged, days_added, days_updated)."""
    merged = {d: dict(v) for d, v in existing.items()}
    added = updated = 0
    for day, vals in incoming.items():
        if day not in merged:
            merged[day] = {}
            added += 1
        else:
            updated += 1
        for laser in LASERS:
            if vals.get(laser) is not None:
                merged[day][laser] = vals[laser]
    # Sort by date
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
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"No raw/ folder found at {RAW_DIR}")
        print("Create it and place CSV exports inside (any nested structure works).")
        return 1

    csv_files = sorted(RAW_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"No CSV files found under {RAW_DIR}")
        return 1

    print(f"Found {len(csv_files)} CSV file(s) under raw/\n")

    by_mode: dict[str, list[Path]] = {"ratio": [], "abs": []}
    for path in csv_files:
        mode = classify_filename(path)
        rel = path.relative_to(SCRIPT_DIR)
        if mode is None:
            print(f"  ?  {rel}  (skipped — filename must contain 'ratio' or 'abs')")
            continue
        by_mode[mode].append(path)
        print(f"  {mode:5s}  {rel}")
    print()

    data = load_existing()
    total_added = total_updated = 0

    for mode, files in by_mode.items():
        if not files:
            continue
        print(f"Processing {mode} files ({len(files)})…")
        combined: dict[str, dict[str, float]] = {}
        for path in files:
            if args.verbose:
                print(f"  • {path.relative_to(SCRIPT_DIR)}")
            file_data = aggregate_csv(path, verbose=args.verbose)
            # Merge files of same mode together first (later files override earlier per day per laser)
            for day, vals in file_data.items():
                if day not in combined:
                    combined[day] = {}
                for laser, v in vals.items():
                    if v is not None:
                        combined[day][laser] = v
        merged, added, updated = merge(data[mode], combined)
        data[mode] = merged
        total_added += added
        total_updated += updated
        print(f"  → {added} new day(s), {updated} updated day(s)")
        print()

    data["updated"] = datetime.now().strftime("%Y-%m-%d")

    print("─" * 50)
    print(f"Summary: {total_added} day(s) added, {total_updated} updated")
    print(f"data.json now contains {len(data['ratio'])} ratio day(s), {len(data['abs'])} abs day(s)")

    if args.dry_run:
        print("\n[dry-run] No changes written.")
        return 0

    with DATA_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
    print(f"\n✓ Written to {DATA_JSON.relative_to(SCRIPT_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
