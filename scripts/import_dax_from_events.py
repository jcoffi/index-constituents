#!/usr/bin/env python3
# Build historical daily DAX snapshots from a CSV of change events (date, added, removed)
# Stops without writing anything if any company name cannot be mapped to an exact .DE ticker.

import os
import sys
import re
import json
import time
import unicodedata
from pathlib import Path
from datetime import date, timedelta
from difflib import SequenceMatcher

import pandas as pd
import requests

# ---------------------------
# Configuration
# ---------------------------
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
DEFAULT_EVENTS_CSV = REPO_ROOT.parent / 'dax_constituents.csv'
DOCS_DIR = REPO_ROOT / 'docs'
FMP_KEY = os.getenv('FMP_API_KEY') or os.getenv('fmp_api_key')

# StockAnalysis listing (Frankfurt Stock Exchange)
STOCKANALYSIS_BASE = 'https://stockanalysis.com/list/frankfurt-stock-exchange/'

# ---------------------------
# Utilities
# ---------------------------
U_MAP = str.maketrans({'Ä':'Ae','Ö':'Oe','Ü':'Ue','ä':'ae','ö':'oe','ü':'ue','ß':'ss'})

def normalize_name(name: str) -> str:
    s = (name or '').translate(U_MAP)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[\.&,'’`\-()\/]+", ' ', s)
    s = re.sub(r"\s+", ' ', s).strip()
    return s

# Conservative acceptance threshold for fuzzy name matching
FUZZY_ACCEPT = 0.90

# We only accept German exchanges
GERMAN_EXCH = {'XETRA', 'FRANKFURT', 'FWB', 'FSE', 'FRA'}

# Known explicit mappings for share classes and common variants
HARDCODED_NAME_TO_DE = {
    'Qiagen NV': 'QIA.DE',
    'Sartorius AG VZ': 'SRT3.DE',
    'Porsche Automobile Holding VZO': 'PAH3.DE',
    'Volkswagen (St)': 'VOW.DE',
    'Volkswagen (Vz)': 'VOW3.DE',
    'Wirecard AG': 'WDI.DE',
}

# Known lineage-based aliases that still preserve correct .DE tickers for DAX context
# Only include when certain. Avoid mapping old entities to successor tickers unless the ticker was
# actually used for DAX membership during the period.
ALIAS_TO_DE = {
    'Deutsche Börse': 'DB1.DE',
    'Hannover Rück SE': 'HNR1.DE',
    'HeidelbergCement': 'HEI.DE',
    'adidas-Salomon': 'ADS.DE',
    'BMW': 'BMW.DE',
    'Infineon': 'IFX.DE',
    'Infineon Technologies AG': 'IFX.DE',
    'Beiersdorf': 'BEI.DE',
    'Deutsche Post': 'DHL.DE',
    'Deutsche Bank': 'DBK.DE',
}

# ---------------------------
# External sources
# ---------------------------

def fmp_search_name(session: requests.Session, query: str):
    # Stable endpoint suggested by user
    url = 'https://financialmodelingprep.com/stable/search-name'
    params = {'query': query, 'limit': 100}
    if FMP_KEY:
        params['apikey'] = FMP_KEY
    r = session.get(url, params=params, timeout=25)
    if r.status_code != 200:
        return []
    try:
        return r.json()
    except Exception:
        return []


def stockanalysis_fetch_all(session: requests.Session) -> list[tuple[str, str]]:
    # Returns list of (symbol, name) from StockAnalysis Frankfurt list across pages
    results: list[tuple[str, str]] = []
    for page in range(1, 50):  # hard cap to avoid infinite loops
        url = STOCKANALYSIS_BASE if page == 1 else f"{STOCKANALYSIS_BASE}?p={page}"
        r = session.get(url, timeout=25)
        if r.status_code != 200:
            break
        html = r.text
        # crude parse: look for table rows with symbol/name anchor structure
        # StockAnalysis commonly uses data embedded in <a href="/stocks/SYMBOL/">SYMBOL</a> and name nearby
        # We use a simple regex; if the structure changes, this may need updating.
        # Example row snippet observed:
        # <a href="/stocks/ALV/">ALV</a> ... <a href="/stocks/ALV/">Allianz SE</a>
        row_pat = re.compile(r"/stocks/([A-Z0-9]{1,6})/\">([^<]{2,100})</a>", re.I)
        hits = row_pat.findall(html)
        if not hits:
            # If this page yields no matches, assume end
            break
        # Heuristic: the list alternates SYMBOL, NAME; we reconstruct pairs
        pairs = []
        for i in range(0, len(hits) - 1, 2):
            sym1, maybe_sym_text = hits[i]
            sym2, maybe_name = hits[i+1]
            # ensure the first looks like ticker itself
            if sym1 == sym2 and maybe_sym_text.upper() == sym1.upper():
                pairs.append((sym1.upper(), maybe_name.strip()))
        if not pairs:
            break
        results.extend(pairs)
        # Sleep lightly to be polite
        time.sleep(0.2)
    return results


# ---------------------------
# Mapping logic
# ---------------------------

def build_name_to_symbol_map(all_names: list[str], current_csv: Path) -> tuple[dict[str,str], list[str], dict[str, list[str]]]:
    # Optional manual overrides
    manual_csv = THIS_DIR / 'dax_name_to_symbol_manual.csv'
    manual_map: dict[str, str] = {}
    if manual_csv.exists():
        try:
            mdf = pd.read_csv(manual_csv)
            for _, r in mdf.iterrows():
                nm = str(r.get('name','')).strip()
                sym = str(r.get('symbol','')).strip()
                if nm and sym and sym.endswith('.DE'):
                    manual_map[nm] = sym
        except Exception:
            pass

    # Returns (name_to_symbol, unresolved_names, debug_info)
    # name_to_symbol maps raw event name -> .DE symbol
    # We keep raw names as keys to avoid accidental merges.
    session = requests.Session()

    # Load current DAX constituents for exact matches
    cur = pd.read_csv(current_csv)
    current_name_to_symbol = dict(zip(cur['Name'].astype(str), cur['Symbol'].astype(str)))

    # Pre-normalized lookup for current names
    norm_current = {normalize_name(k): v for k, v in current_name_to_symbol.items()}

    # StockAnalysis listing (symbol, name) and quick dict by normalized name
    sa_pairs = stockanalysis_fetch_all(session)
    norm_sa = {normalize_name(nm): sym for sym, nm in sa_pairs}

    name_to_symbol: dict[str, str] = {}
    debug: dict[str, list[str]] = {}

    # Stage 0: manual overrides (authoritative)
    name_to_symbol: dict[str, str] = {}
    debug: dict[str, list[str]] = {}
    for nm in all_names:
        if nm in manual_map:
            name_to_symbol[nm] = manual_map[nm]

    # Stage 1: direct, hardcoded, and alias matches
    for nm in all_names:
        if nm in HARDCODED_NAME_TO_DE:
            name_to_symbol[nm] = HARDCODED_NAME_TO_DE[nm]
            continue
        if nm in ALIAS_TO_DE:
            name_to_symbol[nm] = ALIAS_TO_DE[nm]
            continue
        # Exact match to current
        if nm in current_name_to_symbol:
            name_to_symbol[nm] = current_name_to_symbol[nm]
            continue
        # Fuzzy to current names
        nrm = normalize_name(nm)
        if nrm in norm_current:
            name_to_symbol[nm] = norm_current[nrm]
            continue
        # StockAnalysis by normalized name
        if nrm in norm_sa:
            # StockAnalysis symbols are usually base (e.g., ALV) for Frankfurt
            root = norm_sa[nrm].split('.')[0]
            name_to_symbol[nm] = root + '.DE'
            continue

    unresolved = [nm for nm in all_names if nm not in name_to_symbol]

    # Stage 2: FMP search-name for unresolved
    for nm in list(unresolved):
        hits = fmp_search_name(session, nm)
        if not hits:
            debug[nm] = ['fmp:no_hits']
            continue
        # rank by exchange and name similarity
        ranked = []
        nrm = normalize_name(nm)
        for h in hits:
            sym = str(h.get('symbol',''))
            exch = str(h.get('exchangeShortName') or h.get('exchange') or '')
            name_hit = str(h.get('name',''))
            country = str(h.get('country',''))
            score = 0.0
            if exch.upper() in GERMAN_EXCH:
                score += 2.0
            if 'DE' in country.upper() or 'GER' in country.upper():
                score += 1.0
            try:
                score += SequenceMatcher(None, nrm, normalize_name(name_hit)).ratio()
            except Exception:
                pass
            ranked.append((score, name_hit, sym, exch))
        ranked.sort(reverse=True)
        debug[nm] = [f"{s:.2f}|{ex}|{sy}|{nh}" for s, nh, sy, ex in ranked[:5]]
        if ranked:
            s, nh, sy, ex = ranked[0]
            if s >= 2.7 and ex.upper() in GERMAN_EXCH:
                root = sy.split('.')[0].split(':')[0]
                name_to_symbol[nm] = root + '.DE'

    unresolved = [nm for nm in all_names if nm not in name_to_symbol]

    return name_to_symbol, unresolved, debug


# ---------------------------
# Snapshot reconstruction
# ---------------------------

def write_day_snapshot(docs_dir: Path, d: date, code: str, df: pd.DataFrame):
    year_s = f"{d.year:04d}"
    month_s = f"{d.month:02d}"
    day_s = f"{d.day:02d}"
    out_dir = docs_dir / year_s / month_s / day_s
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"constituents-{code}.csv"
    out_json = out_dir / f"constituents-{code}.json"
    dff = df.drop_duplicates(subset=['Symbol']).sort_values('Symbol').reset_index(drop=True)
    dff.to_csv(out_csv, index=False)
    dff.to_json(out_json, orient='records')


def reconstruct_from_events(events_csv: Path, docs_dir: Path, name_to_symbol: dict[str,str]):
    code = 'dax'
    # Load current constituents to get canonical names for known symbols
    cur = pd.read_csv(docs_dir / 'constituents-dax.csv')
    sym_to_name = dict(zip(cur['Symbol'].astype(str), cur['Name'].astype(str)))

    E = pd.read_csv(events_csv)
    E['date'] = pd.to_datetime(E['date']).dt.date
    E['added'] = E['added'].fillna('').astype(str).str.strip()
    E['removed'] = E['removed'].fillna('').astype(str).str.strip()
    E = E.sort_values('date')

    # Build daily membership forward from the first date
    membership: set[str] = set()
    # For initial day, there may be multiple adds
    min_day = E['date'].min()
    max_day = date.today()

    # Build a mapping name->symbol for quick lookup (normalized variants)
    norm_map = {normalize_name(k): v for k, v in name_to_symbol.items()}

    # Apply events by day
    events_by_day = {}
    for d, df in E.groupby('date'):
        events_by_day[d] = df

    cur_day = min_day
    while cur_day <= max_day:
        if cur_day in events_by_day:
            df = events_by_day[cur_day]
            for _, r in df.iterrows():
                add = r['added']
                rem = r['removed']
                if add:
                    sym = name_to_symbol.get(add) or norm_map.get(normalize_name(add))
                    if not sym:
                        raise RuntimeError(f"Unmapped add '{add}' on {cur_day}")
                    membership.add(sym)
                    if sym not in sym_to_name:
                        sym_to_name[sym] = add  # fallback to event name if unknown
                if rem:
                    sym = name_to_symbol.get(rem) or norm_map.get(normalize_name(rem))
                    if not sym:
                        raise RuntimeError(f"Unmapped remove '{rem}' on {cur_day}")
                    membership.discard(sym)
        # Write snapshot for the day if none exists
        day_dir = docs_dir / f"{cur_day.year:04d}" / f"{cur_day.month:02d}" / f"{cur_day.day:02d}"
        if not (day_dir / f"constituents-{code}.csv").exists() and not (day_dir / f"constituents-{code}.json").exists():
            df_out = pd.DataFrame({'Symbol': sorted(membership), 'Name': [sym_to_name.get(s, '') for s in sorted(membership)]})
            write_day_snapshot(docs_dir, cur_day, code, df_out)
        cur_day = cur_day + timedelta(days=1)


# ---------------------------
# Entrypoint
# ---------------------------

def main(argv=None):
    argv = argv or sys.argv[1:]
    events_csv = DEFAULT_EVENTS_CSV
    if not Path(events_csv).exists():
        print(f"Events CSV not found: {events_csv}", file=sys.stderr)
        return 2

    # Load names
    E = pd.read_csv(events_csv)
    names = sorted(set([x for x in (E['added'].fillna('').tolist() + E['removed'].fillna('').tolist()) if x]))

    # Build mapping
    name_to_symbol, unresolved, debug = build_name_to_symbol_map(names, DOCS_DIR / 'constituents-dax.csv')

    # If any unresolved remain, stop and output an audit file for operator review
    if unresolved:
        audit_path = REPO_ROOT / 'scripts' / 'dax_mapping_audit.json'
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump({'unresolved': unresolved, 'debug': debug, 'resolved': name_to_symbol}, f, ensure_ascii=False, indent=2)
        print(f"Unresolved names remain ({len(unresolved)}). Wrote audit to {audit_path}. Aborting without writing snapshots.", file=sys.stderr)
        return 3

    # All names resolved, proceed to reconstruct daily snapshots
    reconstruct_from_events(events_csv, DOCS_DIR, name_to_symbol)
    print('DAX historical snapshots written successfully.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
