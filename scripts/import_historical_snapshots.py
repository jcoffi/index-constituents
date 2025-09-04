#!/usr/bin/env python3
import argparse
from pathlib import Path
from collections import defaultdict
import sys
from datetime import date, timedelta
import pandas as pd

# This script ingests provided Excel files containing index composition change events
# (Added/Removed with dates) and reconstructs monthly constituent snapshots compatible
# with this repository format: docs/YYYY/MM/DD/constituents-<code>.csv and .json.
#
# Supported indices from provided files:
#   - S&P 500          -> code: sp500
#   - NASDAQ-100       -> code: nasdaq100
#   - Dow Jones (DJIA) -> code: dowjones
# Files for unsupported indices (e.g., Russell 3000) are ignored.
#
# Strategy: Build an event list per index, then walk backward month-by-month starting
# from the current constituents (docs/constituents-<code>.csv). For each month, if a
# daily snapshot (YYYY/MM/last-day) already exists we skip it; otherwise we write a
# snapshot for the last calendar day of that month using the current working membership.
# When stepping to the previous month, we invert the events that occurred in the later
# month (remove additions; add back removals).


SUPPORTED_MAP = {
    'S&P 500': 'sp500',
    'NASDAQ-100': 'nasdaq100',
    'DJIA': 'dowjones',
}


def detect_index_and_labels(fname: str):
    f = fname.lower()
    # Return: (index_name, added_top_labels, removed_top_labels, preferred_sheets)
    if 's&p 500' in f or 'sp 500' in f:
        return ('S&P 500', ['Components Added to S&P 500', 'Added to S&P 500'], ['Components Removed from S&P 500', 'Removed from S&P 500'], ['Component Changes'])
    if 'nasdaq 100' in f or 'nasdaq-100' in f:
        return ('NASDAQ-100', ['Added to NASDAQ-100 Index'], ['Removed from NASDAQ-100 Index'], ['NASDAQ-100 Component Changes', 'Component Changes'])
    if 'dow jones' in f or 'djia' in f:
        return ('DJIA', ['Components Added to DJIA', 'Added to DJIA'], ['Components Removed from DJIA', 'Removed from DJIA'], ['Component Changes'])
    # Russell and others currently unsupported for snapshot generation
    return (None, None, None, None)


def read_sheet_with_multiheader(xls: pd.ExcelFile, prefer_sheets=None):
    sheets = prefer_sheets or xls.sheet_names
    for name in sheets:
        try:
            df = pd.read_excel(xls, sheet_name=name, header=[0, 1])
            if df.shape[1] >= 4:
                return df, name
        except Exception:
            pass
        try:
            df = pd.read_excel(xls, sheet_name=name, header=0)
            if df.shape[1] >= 4:
                return df, name
        except Exception:
            pass
    raise RuntimeError("No suitable sheet found in workbook")


def find_date_column(df: pd.DataFrame):
    candidates = {
        'Change Date', 'Date', 'Change  Date', 'Effective Date', 'Index Effective Date',
        'Change date', 'Date Effective', 'Date effective', 'Change', 'ChangeDate'
    }
    if isinstance(df.columns, pd.MultiIndex):
        for col in df.columns:
            for level in col:
                if isinstance(level, str) and level.strip() in candidates:
                    return col
        return df.columns[-1]
    else:
        for col in df.columns:
            if isinstance(col, str) and col.strip() in candidates:
                return col
        return df.columns[-1]


def get_col(df: pd.DataFrame, top_label_candidates, sub_label_candidates):
    if isinstance(df.columns, pd.MultiIndex):
        for top in top_label_candidates:
            for sub in sub_label_candidates:
                for col in df.columns:
                    if (isinstance(col[0], str) and top.lower() in col[0].lower()) and \
                       (isinstance(col[1], str) and sub.lower() == col[1].lower()):
                        return col
        for top in top_label_candidates:
            for col in df.columns:
                if isinstance(col[0], str) and top.lower() in col[0].lower():
                    return col
        return None
    else:
        for sub in sub_label_candidates:
            for col in df.columns:
                if isinstance(col, str) and sub.lower() == col.lower():
                    return col
        for sub in sub_label_candidates:
            for col in df.columns:
                if isinstance(col, str) and sub.lower() in col.lower():
                    return col
        return None


def normalize_events(df: pd.DataFrame, index_name: str, added_top_labels, removed_top_labels, source_file: str) -> pd.DataFrame:
    date_col = find_date_column(df)
    added_ticker_col = get_col(df, added_top_labels, ['Ticker', 'Symbol'])
    added_company_col = get_col(df, added_top_labels, ['Company Name', 'Company', 'Name'])
    removed_ticker_col = get_col(df, removed_top_labels, ['Ticker', 'Symbol'])
    removed_company_col = get_col(df, removed_top_labels, ['Company Name', 'Company', 'Name'])

    records = []
    def to_str(x):
        if pd.isna(x):
            return None
        return str(x).strip()

    for _, row in df.iterrows():
        date_val = row.get(date_col) if not isinstance(date_col, (list, tuple)) else row[date_col]
        try:
            date_parsed = pd.to_datetime(date_val, errors='coerce')
        except Exception:
            date_parsed = pd.NaT

        at = row.get(added_ticker_col) if added_ticker_col is not None else None
        ac = row.get(added_company_col) if added_company_col is not None else None
        if at is not None or ac is not None:
            at_s, ac_s = to_str(at), to_str(ac)
            if at_s or ac_s:
                records.append({
                    'index_name': index_name,
                    'action': 'add',
                    'ticker': at_s,
                    'company': ac_s,
                    'date': date_parsed.normalize() if pd.notna(date_parsed) else pd.NaT,
                    'source_file': source_file,
                })
        rt = row.get(removed_ticker_col) if removed_ticker_col is not None else None
        rc = row.get(removed_company_col) if removed_company_col is not None else None
        if rt is not None or rc is not None:
            rt_s, rc_s = to_str(rt), to_str(rc)
            if rt_s or rc_s:
                records.append({
                    'index_name': index_name,
                    'action': 'remove',
                    'ticker': rt_s,
                    'company': rc_s,
                    'date': date_parsed.normalize() if pd.notna(date_parsed) else pd.NaT,
                    'source_file': source_file,
                })

    out = pd.DataFrame.from_records(records)
    if not out.empty:
        # Clean dashes and blanks
        out['ticker'] = out['ticker'].replace({'-': None, '—': None, '–': None, 'nan': None}).astype('string')
        out['company'] = out['company'].replace({'-': None, '—': None, '–': None, 'nan': None}).astype('string')
        out = out[~(out['ticker'].isna() & out['company'].isna())]
        out = out.dropna(subset=['date'])
        out['date'] = pd.to_datetime(out['date'])
    return out


def parse_events_from_workbook(path: Path) -> pd.DataFrame:
    index_name, added_labels, removed_labels, prefer_sheets = detect_index_and_labels(path.name)
    if not index_name:
        return pd.DataFrame()
    xls = pd.ExcelFile(path)
    df, _ = read_sheet_with_multiheader(xls, prefer_sheets)
    ev = normalize_events(df, index_name, added_labels, removed_labels, path.name)
    if ev.empty and prefer_sheets:
        alt = [s for s in xls.sheet_names if s not in prefer_sheets]
        if alt:
            df2, _ = read_sheet_with_multiheader(xls, alt)
            ev = normalize_events(df2, index_name, added_labels, removed_labels, path.name)
    return ev


def events_by_index(input_dir: Path) -> dict:
    all_files = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in ('.xlsx', '.xls')])
    events = defaultdict(list)
    for p in all_files:
        try:
            ev = parse_events_from_workbook(p)
            if ev is None or ev.empty:
                continue
            idx_name = ev['index_name'].iloc[0]
            if idx_name not in SUPPORTED_MAP:
                continue
            events[idx_name].append(ev)
        except Exception as e:
            print(f"Warning: failed to parse {p.name}: {e}", file=sys.stderr)
    out = {}
    for k, lst in events.items():
        df = pd.concat(lst, ignore_index=True)
        df = df.drop_duplicates(subset=['index_name','action','ticker','company','date','source_file'])
        df = df.sort_values('date')
        out[k] = df
    return out


def load_current_constituents(docs_dir: Path, code: str) -> pd.DataFrame:
    # Use the top-level current constituents snapshot as anchor
    csv_path = docs_dir / f"constituents-{code}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Current constituents file not found: {csv_path}")
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = ['Symbol', 'Name']
    df['Symbol'] = df['Symbol'].astype(str)
    df['Name'] = df['Name'].astype(str)
    return df


def month_key(dt: pd.Timestamp) -> str:
    return dt.strftime('%Y/%m')


def list_existing_month_days(docs_dir: Path, code: str) -> set:
    existing = set()
    base = docs_dir
    if not base.exists():
        return existing
    for ydir in base.iterdir():
        if not ydir.is_dir() or not ydir.name.isdigit() or len(ydir.name) != 4:
            continue
        for mdir in ydir.iterdir():
            if not mdir.is_dir() or len(mdir.name) != 2:
                continue
            for ddir in mdir.iterdir():
                if not ddir.is_dir() or len(ddir.name) != 2:
                    continue
                csv_path = ddir / f"constituents-{code}.csv"
                json_path = ddir / f"constituents-{code}.json"
                if csv_path.exists() or json_path.exists():
                    existing.add(f"{ydir.name}/{mdir.name}/{ddir.name}")
    return existing


def last_day_of_month(year: int, month: int) -> int:
    # Handle month lengths including leap years for February
    if month in (1,3,5,7,8,10,12):
        return 31
    if month in (4,6,9,11):
        return 30
    # February
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 29
    return 28


def write_month_snapshot(docs_dir: Path, ym: str, code: str, df: pd.DataFrame):
    year_s, month_s = ym.split('/')
    year, month = int(year_s), int(month_s)
    day = last_day_of_month(year, month)
    out_dir = docs_dir / year_s / month_s / f"{day:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"constituents-{code}.csv"
    out_json = out_dir / f"constituents-{code}.json"

    # Deduplicate; sort by Symbol for determinism
    dff = df.drop_duplicates(subset=['Symbol']).sort_values('Symbol').reset_index(drop=True)
    dff.to_csv(out_csv, index=False)
    dff.to_json(out_json, orient='records')


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


def reconstruct_daily(docs_dir: Path, idx_name: str, events: pd.DataFrame):
    code = SUPPORTED_MAP[idx_name]
    # Anchor: current constituents
    current_df = load_current_constituents(docs_dir, code)
    symbol_to_name = dict(zip(current_df['Symbol'], current_df['Name']))
    membership = set(current_df['Symbol'].tolist())

    # Group events by exact date (normalized to date)
    ev = events.copy()
    ev['d'] = ev['date'].dt.date
    by_day = {}
    for dkey, dfm in ev.groupby('d'):
        by_day[dkey] = dfm

    if not by_day:
        print(f"No events for {idx_name}; skipping.")
        return

    # Range: from earliest event date to today (UTC)
    min_day = min(by_day.keys())
    today = pd.Timestamp.utcnow().date()

    # Walk backwards day-by-day from today to min_day
    cur = today
    while cur >= min_day:
        # Write snapshot for this day if missing
        day_dir = docs_dir / f"{cur.year:04d}" / f"{cur.month:02d}" / f"{cur.day:02d}"
        out_csv = day_dir / f"constituents-{code}.csv"
        out_json = day_dir / f"constituents-{code}.json"
        if not (out_csv.exists() or out_json.exists()):
            df_out = pd.DataFrame({'Symbol': sorted(membership), 'Name': [symbol_to_name.get(s, '') for s in sorted(membership)]})
            write_day_snapshot(docs_dir, cur, code, df_out)
            print(f"Wrote {day_dir}/constituents-{code}.* (size={len(df_out)})")
        # Invert events of this day to step to previous day
        if cur in by_day:
            dfm = by_day[cur]
            for _, r in dfm.iterrows():
                sym = (r['ticker'] or '').strip() if pd.notna(r['ticker']) else ''
                name = (r['company'] or '').strip() if pd.notna(r['company']) else ''
                if not sym:
                    continue
                if r['action'] == 'add':
                    # Before this day, it was not in the set
                    if sym in membership:
                        membership.remove(sym)
                elif r['action'] == 'remove':
                    # Before this day, it was in the set
                    membership.add(sym)
                    if name and sym not in symbol_to_name:
                        symbol_to_name[sym] = name
        cur = cur - timedelta(days=1)


def main():
    ap = argparse.ArgumentParser(description='Import historical index constituents from Excel change logs into daily snapshots under docs/YYYY/MM/DD.')
    ap.add_argument('--input-dir', default=str(Path(__file__).resolve().parents[1] / '.downloads'), help='Directory containing Excel files (default: repo/.downloads)')
    ap.add_argument('--docs-dir', default=str(Path(__file__).resolve().parents[1] / 'docs'), help='Docs directory (default: repo/docs)')
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    docs_dir = Path(args.docs_dir)

    if not input_dir.exists():
        print(f"Input dir not found: {input_dir}", file=sys.stderr)
        return 1
    docs_dir.mkdir(parents=True, exist_ok=True)
    idx_events = events_by_index(input_dir)
    if not idx_events:
        print("No supported events parsed from inputs.", file=sys.stderr)
        return 2

    for idx_name, ev in idx_events.items():
        try:
            reconstruct_daily(docs_dir, idx_name, ev)
        except Exception as e:
            print(f"Error reconstructing {idx_name}: {e}", file=sys.stderr)

    return 0



    return 0


if __name__ == '__main__':
    raise SystemExit(main())
