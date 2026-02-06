# Backfill Missing Daily Constituents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Backfill missing `docs/YYYY/MM/DD/constituents-<code>.{csv,json}` files based on `supported-indices.csv`, using only existing in-repo data sources.

**Architecture:**
- Audit which daily snapshot files are missing for supported indices.
- Backfill in two tiers:
  - Tier A (true historical): sources that support date-based retrieval (Nasdaq OMX `ExportWeightings` via `tradeDate`).
  - Tier B (derived): sources that do NOT support historical queries; only backfill if we choose a deterministic policy (e.g., copy-current or forward-fill from existing snapshots).

**Tech Stack:** Python 3, `pandas`, `requests`, `openpyxl` (Excel), repository scripts.

---

### Task 1: Establish baseline + quantify missing data

**Files:**
- Read: `supported-indices.csv`
- Read: `docs/`

**Step 1: Audit missing daily files**

Run:

```bash
python3 scripts/audit_missing_daily.py
```

Expected:
- Prints total day directories under `docs/YYYY/MM/DD`.
- Prints per-index counts of missing `csv/json` files from each index start date through the latest day directory.

**Step 2: Decide backfill policy for non-historical sources**

We need an explicit choice for indices whose upstream endpoints are “current-only” (Slickcharts/Bloomberg/CSIndex/SZSE):
- Option 1 (Recommended): backfill ONLY Tier A (Nasdaq OMX) and already-supported in-repo reconstructions (NIFTY weights, US event workbooks if present).
- Option 2: also fill missing daily files by copying the current top-level `docs/constituents-<code>.*` to missing days (not historically accurate).

### Task 2: Add an audit script

**Files:**
- Create: `scripts/audit_missing_daily.py`

**Step 1: Implement audit script**

The script should:
- Parse `supported-indices.csv` start dates (`YYYY/MM` => treat as first day of month).
- Enumerate existing `docs/YYYY/MM/DD` directories.
- For each code, count missing `docs/YYYY/MM/DD/constituents-<code>.csv` and `.json`.
- Print a summary (top missing + totals).

**Step 2: Run it**

Run:

```bash
python3 scripts/audit_missing_daily.py
```

Expected:
- Exit 0 and print missing counts.

### Task 3: Backfill Tier A (Nasdaq OMX) accurately

**Files:**
- Create: `scripts/backfill_nasdaqomx_daily.py`
- Read: `get-constituents.py` (for parsing logic parity)

**Step 1: Implement backfill script**

Requirements:
- Only handle codes whose constituents come from Nasdaq OMX `ExportWeightings` and accept `tradeDate`:
  - `omxs30`, `nqglci`, `nqbr`, `nqbrlc`, `nqca`, `nqcalc`, `nqmx`, `nqmxlc`
- For each code:
  - Determine start date from `supported-indices.csv`.
  - Determine end date as the maximum existing `docs/YYYY/MM/DD` directory.
  - For each day in range, if `constituents-<code>.csv` and `.json` are missing, fetch from Nasdaq OMX using that day as `tradeDate`.
  - Use a lookback window (e.g., 14 days) to handle non-trading days (do NOT assume weekends).
  - Write missing files only; never overwrite existing snapshots.
- Add `--codes`, `--from`, `--to`, `--dry-run`, `--sleep`, `--lookback-days`.

**Step 2: Smoke test on a tiny range**

Run:

```bash
.venv/bin/python scripts/backfill_nasdaqomx_daily.py --codes omxs30 --from 2026-02-01 --to 2026-02-04 --dry-run
.venv/bin/python scripts/backfill_nasdaqomx_daily.py --codes omxs30 --from 2026-02-01 --to 2026-02-04
```

Expected:
- Writes only missing files.
- Produces 30-row OMXS30 files for each day written.

**Step 3: Run the full Tier A backfill**

Run (background):

```bash
PYTHONUNBUFFERED=1 nohup .venv/bin/python scripts/backfill_nasdaqomx_daily.py --sleep 0.2 --lookback-days 14 > backfill-nasdaqomx.log 2>&1 &
```

Expected:
- Long-running job.
- Log shows periodic progress.

### Task 4: Backfill other indices (only if policy allows)

**Files:**
- Use existing scripts if applicable:
  - `scripts/process_weights.py` (NIFTY 50 from `sources/weights.csv`)
  - `scripts/import_historical_snapshots.py` (US indices from event workbooks in `.downloads/`)

**Step 1: NIFTY historical regeneration**

Run:

```bash
python3 scripts/process_weights.py
```

Expected:
- Ensures NIFTY has daily files across the covered range.

**Step 2: US indices from events (optional)**

Only if `.downloads/` contains the Excel workbooks:

```bash
python3 scripts/import_historical_snapshots.py
```

### Task 5: Verify + publish

**Files:**
- Modify: `docs/**` (generated snapshots)

**Step 1: Re-run audit**

Run:

```bash
python3 scripts/audit_missing_daily.py
```

Expected:
- Missing counts drop for Tier A codes.

**Step 2: Commit + PR**

Commit in logical chunks (scripts first, then generated `docs/` backfill) and open a PR.
