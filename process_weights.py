#!/usr/bin/env python3
"""
Process weights.csv to generate historical NIFTY 50 constituent files.
"""

import os
import csv
import json
from datetime import datetime
from pathlib import Path

def parse_weights_csv(weights_file):
    """
    Parse weights.csv and return a dict of date -> list of symbols
    """
    data = {}
    with open(weights_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row['DATE']
            symbols = []
            for key, value in row.items():
                if key != 'DATE':
                    try:
                        weight = float(value)
                        if weight > 0:
                            symbols.append(key)
                    except ValueError:
                        pass  # Skip non-numeric values
            if symbols:
                data[date] = sorted(symbols)  # Sort for consistency
    return data

def create_directory_structure(base_path, date_str):
    """
    Create docs/YYYY/MM/DD/ directory if it doesn't exist
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    day = date_obj.strftime('%d')

    dir_path = Path(base_path) / year / month / day
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def write_csv_file(file_path, symbols):
    """
    Write constituents CSV file
    """
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Symbol', 'Name'])
        for symbol in symbols:
            writer.writerow([symbol, symbol])  # Use symbol as name

def write_json_file(file_path, symbols):
    """
    Write constituents JSON file
    """
    data = [{'Symbol': symbol, 'Name': symbol} for symbol in symbols]
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    weights_file = 'weights.csv'
    docs_dir = 'docs'

    if not os.path.exists(weights_file):
        print(f"Error: {weights_file} not found")
        return

    # Parse the weights data
    date_constituents = parse_weights_csv(weights_file)
    if not date_constituents:
        print("No data found in weights.csv")
        return

    # Sort dates
    sorted_dates = sorted(date_constituents.keys())

    # Process each date
    for date in sorted_dates:
        symbols = date_constituents[date]
        dir_path = create_directory_structure(docs_dir, date)

        csv_file = dir_path / 'constituents-nifty50.csv'
        json_file = dir_path / 'constituents-nifty50.json'

        write_csv_file(csv_file, symbols)
        write_json_file(json_file, symbols)
        print(f"Created files for {date}: {csv_file}, {json_file}")

    # Update top-level files with latest date
    latest_date = sorted_dates[-1]
    latest_symbols = date_constituents[latest_date]

    top_csv = Path(docs_dir) / 'constituents-nifty50.csv'
    top_json = Path(docs_dir) / 'constituents-nifty50.json'

    write_csv_file(top_csv, latest_symbols)
    write_json_file(top_json, latest_symbols)
    print(f"Updated top-level files with data from {latest_date}")

if __name__ == '__main__':
    main()