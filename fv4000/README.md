# FV4000 Laser Power Tracker

Interactive tracker for the Evident FluoView FV4000 (Irchel) laser power monitor (LPM) log. Displays daily mean power per laser line over time, with annotations for known incidents.

**Live:** https://zmb-uzh.github.io/zmb-instruments/fv4000/

## Files

| File | What it is |
|---|---|
| `index.html` | The tracker page. Fetches `data.json` on load. |
| `data.json` | Daily means per laser line. Two sections: `ratio` (% of nominal) and `abs` (detector counts). Regenerated from raw CSVs by `update_data.py`. |
| `update_data.py` | Reads CSV exports from `raw/`, computes daily means, updates `data.json`. |
| `raw/` | Local-only folder for raw CSV exports from the FV4000 software. **Not committed to GitHub** (see root `.gitignore`). |

## Updating the data

1. Export from the FV4000 software with **both** "Power check" and "Power correction" checked. Export once in **Ratio** mode, once in **Absolute** mode.
2. Drop both CSVs into `raw/YYYY-MM-DD/` (use the export date as the folder name).
3. Rename so the filename contains either `ratio` or `abs`, e.g. `laser_FV4000_20260615_ratio.csv` and `laser_FV4000_20260615_abs.csv`.
4. From this folder, run:
   ```
   python update_data.py
   ```
   The script scans every CSV under `raw/` and classifies it by filename. Use `--dry-run` to preview, `--verbose` for per-file details.
5. Commit and push `data.json`:
   ```
   git add data.json
   git commit -m "Update FV4000 data — YYYY-MM-DD"
   git push
   ```
   GitHub Pages updates within a minute.

The `raw/` folder stays local — only the cleaned `data.json` goes to GitHub.

## Data format

`data.json` has the structure:
```json
{
  "ratio": {
    "2026-03-31": {"405": 60.4, "445": 80.4, "488": 51.4, ...},
    ...
  },
  "abs": {
    "2026-03-31": {"405": 3789.2, ...},
    ...
  },
  "updated": "2026-05-29"
}
```

Zeros in the source CSV are treated as "laser off" and excluded from the daily mean.

## CSV upload in the browser

The page also accepts direct CSV upload (two zones: ratio and absolute). These merge into the browser session only — they do not modify `data.json`. Useful for previewing fresh exports before committing.

## Incident annotations

The chart shows colour-coded zones for the 20–27 May 2026 laser misalignment incident:
- Yellow: first realignment 20 May (incomplete)
- Red: 22–26 May, system out of LPM compensation range
- Green: recovery from 27 May onwards

These annotations are currently hardcoded in `index.html`. If future incidents need to be marked, edit the `keyDates` / zones arrays in the chart script.
