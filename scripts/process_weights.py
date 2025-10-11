#!/usr/bin/env python3
"""
Process weights.csv to generate historical NIFTY 50 constituent files.
"""

import os
import csv
import json
from datetime import datetime, timedelta
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
    weights_file = '../sources/weights.csv'
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

    # Process each date range with forward fill
    for i in range(len(sorted_dates) - 1):
        current_date_str = sorted_dates[i]
        next_date_str = sorted_dates[i + 1]
        symbols = date_constituents[current_date_str]

        current_date = datetime.strptime(current_date_str, '%Y-%m-%d')
        next_date = datetime.strptime(next_date_str, '%Y-%m-%d')

        # Create files for current_date
        dir_path = create_directory_structure(docs_dir, current_date_str)
        csv_file = dir_path / 'constituents-nifty50.csv'
        json_file = dir_path / 'constituents-nifty50.json'
        write_csv_file(csv_file, symbols)
        write_json_file(json_file, symbols)
        print(f"Created files for {current_date_str}: {csv_file}, {json_file}")

        # Forward fill for days between current_date + 1 and next_date - 1
        day = current_date + timedelta(days=1)
        fill_count = 0
        while day < next_date:
            date_str = day.strftime('%Y-%m-%d')
            dir_path = create_directory_structure(docs_dir, date_str)
            csv_file = dir_path / 'constituents-nifty50.csv'
            json_file = dir_path / 'constituents-nifty50.json'
            write_csv_file(csv_file, symbols)
            write_json_file(json_file, symbols)
            fill_count += 1
            day += timedelta(days=1)
        if fill_count > 0:
            print(f"Forward filled {fill_count} days from {current_date_str} to {next_date_str}")

    # Process the last date
    last_date_str = sorted_dates[-1]
    symbols = date_constituents[last_date_str]
    dir_path = create_directory_structure(docs_dir, last_date_str)
    csv_file = dir_path / 'constituents-nifty50.csv'
    json_file = dir_path / 'constituents-nifty50.json'
    write_csv_file(csv_file, symbols)
    write_json_file(json_file, symbols)
    print(f"Created files for {last_date_str}: {csv_file}, {json_file}")

    # Update top-level files with latest date
    latest_symbols = symbols  # From last date

    top_csv = Path(docs_dir) / 'constituents-nifty50.csv'
    top_json = Path(docs_dir) / 'constituents-nifty50.json'

    write_csv_file(top_csv, latest_symbols)
    write_json_file(top_json, latest_symbols)
    print(f"Updated top-level files with data from {last_date_str}")

if __name__ == '__main__':
    main()