# AGENTS.md

This repository is a small Python web-scraping + GitHub Pages publishing project.
It downloads index constituents from multiple upstream sites and writes `docs/` CSV/JSON.

If instructions here conflict with repo-provided agent rules, follow the repo rules.

## Repo Rules (Copilot/Cursor)

- Copilot instructions exist at `.github/copilot-instructions.md` and should be treated as canonical.
- No Cursor rules were found (`.cursor/rules/` and `.cursorrules` do not exist).

Key points from `.github/copilot-instructions.md`:

- Python 3.12+ intended; install deps first: `pip install -r requirements.txt`.
- Main command: `./get-constituents.py` (expect minutes; includes sleeps and retries).
- Daily automation: GitHub Actions runs `./update-daily.sh` and commits updated `docs/`.
- No automated tests; validate by running the scripts and checking output files.

## Project Layout

- `get-constituents.py`: main scraper; one function per index; writes `docs/constituents-*.{csv,json}`.
- `supported-indices.csv`: source of truth for supported indices (code/name/start).
- `gen-supported-indices-md.py`: prints a markdown table (to stdout) from `supported-indices.csv`.
- `docs/`: GitHub Pages site and generated data (current + dated snapshots).
- `update-daily.sh`: wrapper that runs `get-constituents.py` then snapshots files into `docs/YYYY/MM/DD/`.
- `update-timestamp.sh` + `gen-footer.py`: update `docs/index.html` footer timestamp.
- `.github/workflows/update-daily.yml`: scheduled daily run and auto-commit.

## Setup

This repo does not ship a virtualenv manager; use a local venv.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Dependencies are in `requirements.txt` (notably: `pandas`, `requests`, `selectorlib`, `fake-useragent`, `openpyxl`, `xlrd`, `tabulate`).

## Build / Lint / Test Commands

There is no formal build system and no dedicated lint/test runner configured.

### "Build" (generate outputs)

- Generate current outputs in `docs/`:

```bash
.venv/bin/python get-constituents.py
```

- Run daily snapshot flow (creates `docs/YYYY/MM/DD/` and copies files):

```bash
bash -lc "source .venv/bin/activate && ./update-daily.sh"
```

- Override snapshot date (UTC) for `update-daily.sh`:

```bash
bash -lc "source .venv/bin/activate && DATE_OVERRIDE=YYYY-MM-DD ./update-daily.sh"
```

### Single "test" (run one index fetch)

No unit tests exist. To validate a single index fetcher, import the script as a module and call one function:

```bash
.venv/bin/python - <<'PY'
import importlib.util

spec = importlib.util.spec_from_file_location('get_constituents', 'get-constituents.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

df = mod.get_constituents_sp500()  # change to the function you are working on
print(df.head())
print('rows', len(df))
PY
```

For Nasdaq OMX indices, call the specific helper, e.g. `get_constituents_nqglci()`.

### "Lint" (lightweight sanity checks)

No linter config exists. Useful sanity checks:

```bash
python3 -m compileall get-constituents.py
```

If you add a lint tool (ruff/black), do it intentionally and wire it via config + CI.

## Working With Generated Files

- `docs/` is primarily generated. Prefer regenerating outputs via scripts instead of hand-editing.
- `gen-supported-indices-md.py` prints the Supported Indices table to stdout; if README needs updating,
  run it and paste/patch the resulting markdown table into `README.md`.

## Coding Style Guidelines

This codebase is script-first and pragmatic. Maintain existing conventions in `get-constituents.py`.

### Imports

- Prefer standard ordering:
  - standard library
  - third-party packages
  - local imports
- Keep imports at top-level (script style); avoid import cycles.

### Formatting

- Keep files UTF-8. Some data/index names include non-ASCII (Chinese names in tables); do not "normalize away".
- Indentation: 4 spaces.
- Keep shebangs as-is (`#!/usr/bin/env python3`) and preserve executable scripts.

### Naming

- Functions: `snake_case`.
- Index fetchers follow `get_constituents_<code>()`.
- Shared helpers follow `get_constituents_from_<source>()`.

### Data schema

- Each fetcher should return a `pandas.DataFrame` with *exactly*:
  - `Symbol`
  - `Name`
- Symbols must match Yahoo Finance conventions when a mapping is known (suffixes like `.SZ`, `.SS`, `.HK`, `.L`, etc.).
- If a suffix is not reliably derivable from the upstream export, prefer leaving the symbol as-is rather than guessing.

### Networking and scraping

- Always send a reasonable `User-Agent` (the project uses `fake-useragent`).
- Prefer explicit timeouts for HTTP calls when using `requests`.
- Expect upstream HTML to change; selectors can break.
- Avoid hammering upstream sites: respect existing sleeps and retry/backoff behavior.

### Error handling

- Fetching is "best effort": individual index failures should not crash the entire run.
- Per-index retry loops exist in `__main__`; keep them consistent when adding new indices.
- If a parser yields no rows, raise a clear `ValueError` (so retries occur and logs are actionable).

### Types

- No type checking is configured. Keep code readable; add type hints only when they clarify non-obvious logic.

## Adding a New Index (Checklist)

1. Add a row to `supported-indices.csv` (Code, Name, Start).
2. Implement `get_constituents_<code>()` in `get-constituents.py`.
3. Wire it into the `__main__` section so outputs are written to:
   - `docs/constituents-<code>.csv`
   - `docs/constituents-<code>.json`
4. Regenerate outputs: `.venv/bin/python get-constituents.py`.
5. Update `README.md` Supported Indices table by running:
   - `.venv/bin/python gen-supported-indices-md.py` (then paste/patch output).
6. If the website list (`docs/index.html`) is meant to include the new index, update it consistently.

## Secrets and Credentials

- Do not commit tokens or `.env` files.
- If you need GitHub auth locally, prefer `gh auth login` or environment-provided tokens.
