#!/bin/sh
# Run in UTC to align with GitHub Actions schedule window (20:00–23:00 UTC)
year=$(date -u +%Y)
month=$(date -u +%m)
day=$(date -u +%d)
echo "Current Year  : $year"
echo "Current Month : $month"
echo "Current Day   : $day"

# create directory for current day
mkdir -p docs/$year/$month/$day

# retrieve data
./get-constituents.py

# copy files into daily folder
cp docs/*.json docs/$year/$month/$day
cp docs/*.csv docs/$year/$month/$day
