#!/usr/bin/env python3
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

# Overrides and manual mappings for missing/incorrect ones
overrides = {
    "Intermediate Capital Group": "ICG",
    "Intermediate Capital Grup": "ICG",
    "Marks & Spencer Group": "MKS",
    "Howden Joinery Group": "HWDN",
    "British Land Co": "BLND",
    "British Land Co.": "BLND",
    "Smith (DS)": "SMDS",
    "Hargreaves Lansdown": "HL",
    "Diploma": "DPLM",
    "Abrdn": "ABDN",
    "Hiscox": "HSX",
    "Hikma Pharmaceuticals": "HIK",
    "Johnson Matthey": "JMAT",
    "Dechra Pharmaceuticals": "DPH",
    "Easyjet": "EZJ",
    "Endeavour Mining": "EDV",
    "Flutter Entertainment": "FLTR",
    "Darktrace": "DARK",
    "LondonMetric Property": "LMP",
    "RS Group": "RS1",
    "Vistry Group": "VTY",
    "St. James's Place": "STJ",
    "Smurfit Kappa Group": "SKG",
    "Burberry Group": "BRBY",
    "B&M European Value Retail": "BME",
    "Alliance Witan": "ALW",
    "Games Workshop Group": "GAW",
    "Polar Capital Technology Trust": "PCT",
    "Coca-Cola Europacific Partners": "CCEP",
    "Babcock International Group": "BAB",
    "Taylor Wimpey": "TW",
    "Unite Group": "UTG",
    "Metlen Energy & Metals": "MTLN",
    "WPP": "WPP",
    "Valterra Platinum Distribution Line": "VALT_TEMP",
    "The Magnum Ice Cream Company": "MAGNUM_TEMP"
}
name_to_ticker.update(overrides)

# Load changes
df_changes = pd.read_csv(changes_csv)
df_changes['Date'] = pd.to_datetime(df_changes['Date'], format='%d-%b-%y', errors='coerce')
df_changes = df_changes.dropna(subset=['Date']).sort_values('Date', ascending=False)

# Find latest FTSE100 file
latest_date = None
latest_df = None
today = datetime.now()
for i in range(30):
    dt = today - timedelta(days=i)
    path = Path(base_dir) / dt.strftime('%Y/%m/%d') / 'constituents-ftse100.csv'
    if path.exists():
        latest_date = datetime(dt.year, dt.month, dt.day)
        latest_df = pd.read_csv(path)
        print(f"Base composition from {latest_date.date()}: {len(latest_df)} constituents")
        break

if latest_df is None:
    print("No existing FTSE100 data found in the last 30 days")
    exit(1)

# FTSE100 start date
start_date = datetime(2023, 7, 1)

current_df = latest_df.copy()
current_date = latest_date

# Helper to normalize ticker
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
        print(f"Processing {len(day_changes)} changes for {current_date.date()}:")
        for _, row in day_changes.iterrows():
            added = str(row['Added']).strip() if pd.notna(row['Added']) else None
            deleted = str(row['Deleted']).strip() if pd.notna(row['Deleted']) else None
            
            # Walking backward:
            if added:
                ticker_add = normalize_ticker(added)
                if ticker_add and ticker_add in current_df['Symbol'].values:
                    current_df = current_df[current_df['Symbol'] != ticker_add]
                    print(f"  Backward: Removed {ticker_add} ({added})")
                elif ticker_add:
                    print(f"  Warning: {ticker_add} ({added}) not found in composition on {current_date.date()}")
            
            if deleted:
                ticker_del = normalize_ticker(deleted)
                if ticker_del and ticker_del not in current_df['Symbol'].values:
                    new_row = pd.DataFrame({'Symbol': [ticker_del], 'Name': [deleted]})
                    current_df = pd.concat([current_df, new_row], ignore_index=True)
                    print(f"  Backward: Added {ticker_del} ({deleted})")

    # Standardize DF
    current_df = current_df[['Symbol', 'Name']].sort_values('Symbol').drop_duplicates().reset_index(drop=True)

    # We skip writing if file exists, but we MUST update current_df anyway to maintain state
    if not csv_path.exists():
        os.makedirs(dir_path, exist_ok=True)
        current_df.to_csv(csv_path, index=False)
        
        # Write JSON
        records = current_df.to_dict('records')
        with open(json_path, 'w') as f:
            json.dump(records, f, indent=2)
        
        if len(current_df) != 100:
            print(f"Created {date_str} (WARNING: {len(current_df)} symbols)")
        elif current_date.day == 1:
            print(f"Created {date_str} (100 symbols)")

    current_date -= timedelta(days=1)

print(f"✓ Backfill complete for FTSE100")
