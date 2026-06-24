# FV4000 Laser Power Tracker

Interactive tracker for the laser power monitor (LPM) log of **CLSM - Evident Fluoview 4000 (Irchel)** — the Evident FluoView FV4000 confocal at the Center for Microscopy and Image Analysis, University of Zurich (referred to as **FV4000** below). Plots power per laser line **per measurement session** over time, with annotations for known incidents.

**Live:** https://zmb-uzh.github.io/zmb-instruments/fv4000/

## Files

| File | What it is |
|---|---|
| `index.html` | The tracker page. Fetches `data.json` on load. |
| `data.json` | One point **per measurement session** per laser line (the session median). Two sections: `ratio` (% of nominal) and `abs` (detector counts). Regenerated from raw CSVs by `update_data.py`. |
| `update_data.py` | Reads CSV exports from `raw/`, groups readings into sessions, writes `data.json`. Standard library only — no install needed. |
| `raw/` | Local-only folder for raw CSV exports, one subfolder per export date. **Not committed to GitHub** (see root `.gitignore`). |

## What "per session" means

The FV4000 software logs many readings per laser per day (during warm-up and across separate checks). Rather than flattening each day to a single mean — which hid real intra-day changes — readings are split into **sessions**: a new session starts whenever there is a gap of more than `SESSION_GAP_MINUTES` (default **30 min**) between consecutive readings. Each laser line in a session is summarised by the **median** of that session's readings. So a day with a morning and an afternoon check shows up as two points.

## Updating the data (staff)

1. In the FV4000 software, export the LPM log with **both** "Power check" and "Power correction" checked. Export once in **Ratio** mode and once in **Absolute** mode.
2. Create a new dated subfolder `raw\YYYY-MM-DD\` (use the export date) and drop both CSVs in. **Keep the previous folders** — see the note below.
3. Make sure each filename contains `ratio` or `abs` (e.g. `laser_FV4000_20260715_ratio.csv`, `laser_FV4000_20260715_abs.csv`). The date in the filename doesn't matter — dates are read from inside the CSV.
4. From this folder, run:
   ```
   python update_data.py
   ```
   Add `--dry-run` to preview without writing, `--verbose` for per-file detail. The script scans every CSV under `raw/`, pools the readings, and rebuilds the sessions.
5. Reload the local page to check it looks right (see *Viewing* below), then commit and push **only** `data.json`. The script prints the exact command to run — copy it from the last lines of its output:
   ```
   git add fv4000/data.json
   git commit -m "Update FV4000 data - 2026-06-23"   ← date filled in by the script
   git push
   ```
   GitHub Pages updates within a minute.

> **Keep every dated export folder.** Each FV4000 export is *cumulative* (it contains the whole history) but can occasionally drop the earliest readings. `update_data.py` pools all folders and de-duplicates by timestamp, so keeping them all guarantees no history is lost. `raw/` is local-only (gitignored), so this costs nothing in the repository.

> `python update_data.py --rebuild` rebuilds `data.json` from `raw/` only, ignoring the committed file. Use it for a clean full rebuild **when `raw/` holds all exports** — never on a fresh clone (where `raw/` is empty), or you would wipe the published history.

## Viewing

- **Time range:** the `1M / 3M / 6M / All` buttons limit the chart to a recent window so it stays readable as data accumulates (the window is anchored to the most recent session).
- **Mode:** toggle `% of nominal` ↔ `Absolute counts`.
- **Lasers:** toggle individual laser lines on/off.
- To preview locally you must **serve the folder** (the page uses `fetch('./data.json')`, which browsers block over `file://`):
  ```
  python -m http.server 8000
  ```
  then open `http://localhost:8000/`. Opening `index.html` directly will not load `data.json`.

## Data format

```json
{
  "ratio": {
    "2026-03-31T14:25:40": {"405": 60.4, "445": 80.4, "488": 51.4, "...": null},
    "2026-04-01T08:26:01": {"405": 66.0, "...": null}
  },
  "abs":   { "2026-03-31T14:25:40": {"405": 3789.2} },
  "updated": "2026-06-02"
}
```
Keys are session start timestamps. Zeros in the source CSV are treated as "laser off" and excluded from the session median. A laser not measured in a session is `null`.

## CSV upload in the browser

The page also accepts direct CSV upload (two zones: ratio and absolute). Uploaded data is sessionised the same way but lives in the browser only — it does **not** modify `data.json`. Useful for previewing a fresh export before committing.

## Incident annotations

The chart shows colour-coded zones for the 20–27 May 2026 laser misalignment incident (yellow = first realignment 20 May; red = 22–26 May out of LPM range; green = recovery from 27 May). These are hardcoded in `index.html`; to mark future incidents, edit the `keyDates` / zone arrays in the chart script.

## Tuning (maintainers)

- **Session split:** `SESSION_GAP_MINUTES` in `update_data.py` and `SESSION_GAP_MS` in `index.html` — keep the two in sync.
- **Representative value:** currently the per-session median; change in `sessionize()` (`update_data.py`) and `parseCSV()` (`index.html`) if a different statistic (e.g. last stabilised reading) is preferred.
