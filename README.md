# ZMB Instruments

Per-instrument operational status pages and tools for the Center for Microscopy and Image Analysis (ZMB), University of Zurich.

This repository hosts lightweight HTML status pages for individual instruments at the ZMB core facility. Each page is self-contained, browser-based, and published via GitHub Pages so it can be embedded in the ZMB instrument webpages or accessed directly.

**Live site:** https://zmb-uzh.github.io/zmb-instruments/

## What's here

| Instrument | Page | Description |
|---|---|---|
| CLSM - Evident Fluoview 4000 (Irchel) | [fv4000/](fv4000/) | Laser power monitor (LPM) tracker — per-session power per laser line over time, with incident annotations |

More instruments will be added as the need arises.

## Scope

This repo is the **operational, user-facing** side of ZMB tooling — status pages, calibration histories, on-instrument guidance. It is intentionally separate from the ZMB Knowledge Base pipeline (training records, bookings, dashboards), which has stricter data governance and is not public.

**What goes here:**
- Per-instrument status visualisations (laser power, calibration drift, etc.)
- Operational reference content useful to instrument users
- Anything that benefits from being browser-accessible and embeddable

**What does not go here:**
- User booking data, names, or personal identifiers


## How each instrument folder is organised

Each instrument has its own folder containing a self-contained `index.html`:

```
<instrument-name>/
  index.html        ← the tracker / status page
  data.json         ← cleaned data the page reads on load (optional, depends on page)
  update_data.py    ← script that regenerates data.json from raw exports (optional)
  raw/              ← local-only raw data, .gitignored
  README.md         ← how to update this specific page
```

See `fv4000/README.md` for a complete example.

## Adding a new instrument

1. Create a folder named after the instrument: `<instrument-name>/`
2. Build `index.html` as a self-contained page (use the `fv4000/` page as a template)
3. If the page needs source data, follow the `data.json` + `update_data.py` + `raw/` pattern
4. Add a `README.md` describing how to update it
5. Add an entry to the table above
6. Commit and push — GitHub Pages serves the new page automatically at `https://zmb-uzh.github.io/zmb-instruments/<instrument-name>/`


## License

BSD 3-Clause. See `LICENSE`.

## Maintainer

ZMB Core Facility — University of Zurich
