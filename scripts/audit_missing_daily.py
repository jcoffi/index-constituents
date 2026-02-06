#!/usr/bin/env python3

"""Audit missing daily constituent snapshots.

Counts missing `docs/YYYY/MM/DD/constituents-<code>.{csv,json}` files for each index in
`supported-indices.csv`, from its start date through the latest existing daily directory.

This is a reporting script only; it never writes files.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pandas as pd


DAY_DIR_RE = re.compile(r'^\d{4}/\d{2}/\d{2}$')


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


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    supported_csv = repo_root / 'supported-indices.csv'
    docs_dir = repo_root / 'docs'

    df = pd.read_csv(supported_csv)
    df.columns = [c.strip() for c in df.columns]
    df['Code'] = df['Code'].astype(str).str.strip()
    df['Start'] = df['Start'].astype(str).str.strip()

    day_list = list_daily_dirs(docs_dir)
    print(f'day_dirs {len(day_list)}')
    if not day_list:
        return 0
    print(f'min_day {day_list[0]} max_day {day_list[-1]}')

    results: list[tuple[str, int, int]] = []
    total_missing = 0

    for r in df.itertuples(index=False):
        code = str(r.Code).strip()
        start = parse_start_date(str(r.Start))
        missing = 0
        checked_days = 0

        for day in day_list:
            if day < start:
                continue
            checked_days += 1
            day_dir = docs_dir / f'{day.year:04d}' / f'{day.month:02d}' / f'{day.day:02d}'
            if not (day_dir / f'constituents-{code}.csv').exists():
                missing += 1
            if not (day_dir / f'constituents-{code}.json').exists():
                missing += 1

        results.append((code, missing, checked_days))
        total_missing += missing

    results.sort(key=lambda x: x[1], reverse=True)

    print('top missing:')
    for code, missing, checked in results[:15]:
        print(f'{code:10s} missing_files={missing} days_checked={checked}')
    print(f'total missing files {total_missing}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
