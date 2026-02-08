#!/usr/bin/env python3
"""
Backfill FTSE 100 historical data from change events (1984 onwards).
"""

import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Paths
changes_csv = 'sources/ftse100_all_changes.csv'
mapping_json = 'sources/ftse100_name_to_ticker_all.json'
base_dir = 'docs'

# Load mappings
with open(mapping_json, 'r') as f:
    name_to_ticker = json.load(f)

# Overrides
overrides = {
    "BT Group": "BT/A", "British Telecom": "BT/A", "British Telecommunications": "BT/A",
    "BP": "BP/", "BP PLC": "BP/", "Rolls Royce": "RR/", "Rolls-Royce": "RR/", "Rolls-Royce Holdings": "RR/",
    "Shell": "SHEL", "Royal Dutch Shell": "SHEL", "Royal Dutch Shell A&B": "SHEL", "Royal Dutch Shell B": "SHEL",
    "Intermediate Capital Group": "ICG", "Intermediate Capital Grup": "ICG",
    "Marks & Spencer Group": "MKS", "Marks and Spencer Group": "MKS", "M&S": "MKS",
    "Howden Joinery Group": "HWDN", "British Land Co": "BLND", "British Land Co.": "BLND",
    "Smith (DS)": "SMDS", "Hargreaves Lansdown": "HL.", "BHP Group Plc": "BHP",
    "Rio Tinto": "RIO", "GlaxoSmithKline": "GSK", "AstraZeneca": "AZN",
    "Vodafone": "VOD", "Vodafone Group": "VOD", "WPP Group": "WPP",
    "3i Group": "III", "BAA": "BAA", "GKN": "GKN", "GKN PLC": "GKN",
    "BT.A": "BT/A", "BP.": "BP/", "RR.": "RR/", "JD.": "JD/", "SN.": "SN/",
    "JE.": "JE/", "DC.": "DC/", "BG.": "BG/", "NG.": "NG/", "NWG": "NWG",
}
name_to_ticker.update(overrides)

# Load changes
df_changes = pd.read_csv(changes_csv)
df_changes['Date'] = pd.to_datetime(df_changes['Date'], format='%d-%b-%y', errors='coerce')
df_changes = df_changes.dropna(subset=['Date']).sort_values('Date', ascending=False)

# Find latest FTSE100 file
latest_date = None
latest_symbols = set()
latest_names = {} # symbol -> name mapping

today = datetime.now()
for i in range(60):
    dt = today - timedelta(days=i)
    path = Path(base_dir) / dt.strftime('%Y/%m/%d') / 'constituents-ftse100.csv'
    if path.exists():
        latest_date = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        df = pd.read_csv(path)
        latest_symbols = set(df['Symbol'].tolist())
        for _, row in df.iterrows():
            latest_names[row['Symbol']] = row['Name']
        print(f"Base composition from {latest_date.date()}: {len(latest_symbols)} constituents")
        break

if latest_date is None:
    print("No existing FTSE100 data found in the last 60 days")
    exit(1)

# FTSE100 start date
start_date = datetime(1984, 1, 3)

current_symbols = latest_symbols.copy()
current_names = latest_names.copy()
current_date = latest_date

def normalize_ticker(name):
    ticker = name_to_ticker.get(name)
    if ticker and not ticker.endswith('.L'):
        return ticker + '.L'
    return ticker

while current_date >= start_date:
    date_str = current_date.strftime('%Y/%m/%d')
    dir_path = Path(base_dir) / date_str
    csv_path = dir_path / 'constituents-ftse100.csv'
    json_path = dir_path / 'constituents-ftse100.json'
    
    # Identify changes on this day
    day_changes = df_changes[df_changes['Date'] == current_date]
    if not day_changes.empty:
        for _, row in day_changes.iterrows():
            added = str(row['Added']).strip() if pd.notna(row['Added']) else None
            deleted = str(row['Deleted']).strip() if pd.notna(row['Deleted']) else None
            
            # Walking backward
            if added:
                t_add = normalize_ticker(added)
                if t_add in current_symbols:
                    current_symbols.remove(t_add)
            if deleted:
                t_del = normalize_ticker(deleted)
                if t_del:
                    current_symbols.add(t_del)
                    current_names[t_del] = deleted

    if not csv_path.exists():
        os.makedirs(dir_path, exist_ok=True)
        
        # Prepare data
        sorted_symbols = sorted(list(current_symbols))
        out_rows = []
        for s in sorted_symbols:
            name = current_names.get(s, s)
            out_rows.append({'Symbol': s, 'Name': name})
        
        out_df = pd.DataFrame(out_rows)
        out_df.to_csv(csv_path, index=False)
        with open(json_path, 'w') as f:
            json.dump(out_rows, f, indent=2)
            
        if current_date.day == 1 or len(current_symbols) != 100:
            print(f"Created {date_str} ({len(current_symbols)} symbols)")

    current_date -= timedelta(days=1)

print("✓ FTSE100 full history backfill complete")
