#!/usr/bin/env python3

"""Backfill missing daily snapshots for Nasdaq OMX ExportWeightings indices.

Writes missing files under:
  docs/YYYY/MM/DD/constituents-<code>.csv
  docs/YYYY/MM/DD/constituents-<code>.json

Only fills files that are missing; never overwrites existing snapshots.

This script uses only the Nasdaq OMX endpoint already used in `get-constituents.py`:
  https://indexes.nasdaqomx.com/Index/ExportWeightings/<symbol>?tradeDate=YYYY-MM-DDT00:00:00.000&timeOfDay=EOD
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from fake_useragent import UserAgent


ua = UserAgent()


DAY_DIR_RE = re.compile(r'^\d{4}/\d{2}/\d{2}$')


@dataclass(frozen=True)
class NasdaqOmxCfg:
    code: str
    index_symbol: str
    suffix: str


NASDAQ_OMX: dict[str, NasdaqOmxCfg] = {
    'omxs30': NasdaqOmxCfg(code='omxs30', index_symbol='OMXS30', suffix='.ST'),
    'nqglci': NasdaqOmxCfg(code='nqglci', index_symbol='NQGLCI', suffix=''),
    'nqbr': NasdaqOmxCfg(code='nqbr', index_symbol='NQBR', suffix='.SA'),
    'nqbrlc': NasdaqOmxCfg(code='nqbrlc', index_symbol='NQBRLC', suffix='.SA'),
    'nqca': NasdaqOmxCfg(code='nqca', index_symbol='NQCA', suffix='.TO'),
    'nqcalc': NasdaqOmxCfg(code='nqcalc', index_symbol='NQCALC', suffix='.TO'),
    'nqmx': NasdaqOmxCfg(code='nqmx', index_symbol='NQMX', suffix='.MX'),
    'nqmxlc': NasdaqOmxCfg(code='nqmxlc', index_symbol='NQMXLC', suffix='.MX'),
}


def parse_start_date(s: str) -> dt.date:
    s = str(s).strip()
    for fmt in ('%Y/%m/%d', '%Y/%m'):
        try:
            d = dt.datetime.strptime(s, fmt).date()
            if fmt == '%Y/%m':
                return d.replace(day=1)
            return d
        except ValueError:
            continue
    raise ValueError(f'Unsupported start date format: {s!r}')


def normalize_symbol(symbol: object) -> str:
    s = str(symbol).strip().upper()
    s = s.replace(' ', '-')
    return s


def list_daily_dirs(docs_dir: Path) -> list[dt.date]:
    days: list[dt.date] = []
    for p in docs_dir.glob('*/*/*'):
        if not p.is_dir():
            continue
        rel = p.relative_to(docs_dir).as_posix()
        if not DAY_DIR_RE.match(rel):
            continue
        try:
            y, m, d = (int(x) for x in rel.split('/'))
            days.append(dt.date(y, m, d))
        except Exception:
            continue
    days.sort()
    return days


def fetch_export(index_symbol: str, suffix: str, trade_date: dt.date, lookback_days: int) -> pd.DataFrame:
    last_exc: Exception | None = None
    for i in range(lookback_days + 1):
        d = trade_date - dt.timedelta(days=i)
        url = (
            'https://indexes.nasdaqomx.com/Index/ExportWeightings/'
            f'{index_symbol}?tradeDate={d:%Y-%m-%d}T00:00:00.000&timeOfDay=EOD'
        )

        try:
            headers = {'User-Agent': ua.random}
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            if not r.content:
                raise ValueError('Empty response')

            df_raw = pd.read_excel(io.BytesIO(r.content), header=None)
            header_row = None
            for ridx, row in df_raw.iterrows():
                if 'Company Name' in row.values and 'Security Symbol' in row.values:
                    header_row = int(ridx)
                    break
            if header_row is None:
                raise ValueError('Header row not found')

            df = pd.read_excel(io.BytesIO(r.content), header=header_row)
            if 'Security Symbol' not in df.columns or 'Company Name' not in df.columns:
                raise ValueError(f'Unexpected columns: {list(df.columns)}')

            df = df[['Security Symbol', 'Company Name']].copy()
            df.columns = ['Symbol', 'Name']
            df['Symbol'] = [normalize_symbol(x) + suffix for x in df['Symbol'].tolist()]

            if df.empty:
                raise ValueError('Empty constituents file')

            return df
        except Exception as e:
            last_exc = e
            continue

    raise RuntimeError(f'Failed to fetch {index_symbol} for {trade_date}: {last_exc}')


def write_snapshot(docs_dir: Path, day: dt.date, code: str, df: pd.DataFrame) -> None:
    out_dir = docs_dir / f'{day.year:04d}' / f'{day.month:02d}' / f'{day.day:02d}'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f'constituents-{code}.csv'
    out_json = out_dir / f'constituents-{code}.json'

    dff = df.drop_duplicates(subset=['Symbol']).sort_values('Symbol').reset_index(drop=True)
    dff.to_csv(out_csv, index=False)
    dff.to_json(out_json, orient='records')


def main() -> int:
    ap = argparse.ArgumentParser(description='Backfill missing daily Nasdaq OMX constituent snapshots.')
    ap.add_argument('--docs-dir', default='docs', help='Docs directory (default: docs)')
    ap.add_argument('--supported-indices', default='supported-indices.csv', help='CSV file (default: supported-indices.csv)')
    ap.add_argument('--codes', default='', help='Comma-separated codes (default: all supported Nasdaq OMX codes)')
    ap.add_argument('--from', dest='from_date', default='', help='Override start date YYYY-MM-DD (default: from supported-indices.csv)')
    ap.add_argument('--to', dest='to_date', default='', help='Override end date YYYY-MM-DD (default: latest docs day directory)')
    ap.add_argument('--lookback-days', type=int, default=14, help='Lookback days for non-trading days (default: 14)')
    ap.add_argument('--sleep', type=float, default=0.2, help='Base sleep seconds between requests (default: 0.2)')
    ap.add_argument('--dry-run', action='store_true', help='Report what would be written without writing')
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    docs_dir = (repo_root / args.docs_dir).resolve()
    supported_csv = (repo_root / args.supported_indices).resolve()

    df = pd.read_csv(supported_csv)
    df.columns = [c.strip() for c in df.columns]
    start_map = {str(r.Code).strip(): parse_start_date(str(r.Start)) for r in df.itertuples(index=False)}

    if args.codes.strip():
        codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    else:
        codes = sorted(NASDAQ_OMX.keys())

    unknown = [c for c in codes if c not in NASDAQ_OMX]
    if unknown:
        raise SystemExit(f'Unsupported code(s): {unknown}. This script only handles: {sorted(NASDAQ_OMX.keys())}')

    day_list = list_daily_dirs(docs_dir)
    if not day_list:
        raise SystemExit(f'No daily directories found under {docs_dir}')

    max_day = day_list[-1]
    to_day = dt.datetime.strptime(args.to_date, '%Y-%m-%d').date() if args.to_date else max_day

    total_missing_days = 0
    total_requests = 0
    total_written = 0

    for code in codes:
        cfg = NASDAQ_OMX[code]
        start = dt.datetime.strptime(args.from_date, '%Y-%m-%d').date() if args.from_date else start_map[code]
        if start > to_day:
            continue

        missing_days = 0
        for day in day_list:
            if day < start or day > to_day:
                continue
            day_dir = docs_dir / f'{day.year:04d}' / f'{day.month:02d}' / f'{day.day:02d}'
            out_csv = day_dir / f'constituents-{code}.csv'
            out_json = day_dir / f'constituents-{code}.json'
            if out_csv.exists() and out_json.exists():
                continue

            missing_days += 1
            total_missing_days += 1

            if args.dry_run:
                continue

            total_requests += 1
            df_out = fetch_export(cfg.index_symbol, cfg.suffix, trade_date=day, lookback_days=args.lookback_days)
            write_snapshot(docs_dir, day, code, df_out)
            total_written += 1

            # Be polite to upstream; add small jitter.
            sleep_s = max(0.0, args.sleep) + random.random() * 0.10
            if sleep_s:
                time.sleep(sleep_s)

            if total_written % 500 == 0:
                print(f'progress written={total_written} requests={total_requests}')

        print(f'{code}: missing_days={missing_days}')

    print(f'total_missing_days {total_missing_days}')
    if not args.dry_run:
        print(f'total_written {total_written}')
        print(f'total_requests {total_requests}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
