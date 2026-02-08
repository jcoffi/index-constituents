#!/usr/bin/env python3
import pandas as pd
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

def parse_nse_file(filename):
    symbols = []
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        return pd.DataFrame(columns=['Symbol', 'Name'])
        
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Try to find header
    header_idx = -1
    for i, line in enumerate(lines):
        if 'Security Symbol' in line or 'Symbol' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        # Fallback for some files that have specific formats
        for i, line in enumerate(lines):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) > 1 and parts[0] == '1':
                header_idx = i - 1
                break

    for line in lines[header_idx+1:]:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) > 1 and parts[0].isdigit():
            symbol = parts[1]
            if symbol and not symbol.startswith('DUMMY'):
                symbols.append(symbol)
    
    return pd.DataFrame({'Symbol': sorted(symbols), 'Name': sorted(symbols)})

def backfill_range(df, year, month, start_day, end_day):
    created = 0
    if df.empty:
        return 0
    for day in range(start_day, end_day + 1):
        date_str = f"{year}/{month:02d}/{day:02d}"
        dir_path = Path('docs') / date_str
        csv_path = dir_path / 'constituents-nifty50.csv'
        if not csv_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv_path, index=False)
            with open(dir_path / 'constituents-nifty50.json', 'w') as f:
                json.dump(df.to_dict('records'), f, indent=2)
            created += 1
    return created

def extract_local(name):
    print(f"Extracting {name} from sources...")
    zip_path = f"sources/mcwb_{name}.zip"
    if not os.path.exists(zip_path):
        print(f"Error: {zip_path} not found")
        return False
    subprocess.run(['unzip', '-o', zip_path], capture_output=True)
    print(f"Extracted {name}")
    return True

def main():
    # Jan 2008
    if extract_local('jan08'):
        # Jan 2008 file name is usually niftymcwb.csv
        df_jan08 = parse_nse_file('niftymcwb.csv')
        c = backfill_range(df_jan08, 2008, 1, 1, 31)
        print(f"Created {c} snapshots for Jan 2008")

    # Sep 2025
    if extract_local('sep25'):
        # 2025 files are usually nifty50_mcwb.csv
        df_sep25 = parse_nse_file('nifty50_mcwb.csv')
        c = backfill_range(df_sep25, 2025, 9, 1, 30)
        print(f"Created {c} snapshots for Sep 2025")

    # Oct 2025
    if extract_local('oct25'):
        df_oct25 = parse_nse_file('nifty50_mcwb.csv')
        c = backfill_range(df_oct25, 2025, 10, 1, 31)
        print(f"Created {c} snapshots for Oct 2025")

    # Dec 2025
    if extract_local('dec25'):
        df_dec25 = parse_nse_file('nifty50_mcwb.csv')
        c = backfill_range(df_dec25, 2025, 12, 28, 28)
        print(f"Created {c} snapshots for Dec 2025")

if __name__ == '__main__':
    main()
