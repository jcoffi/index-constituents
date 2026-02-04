#!/bin/sh
# Run in UTC to align with GitHub Actions schedule window (20:00–23:00 UTC)
if [ -n "$DATE_OVERRIDE" ]; then
  year=$(date -u -d "$DATE_OVERRIDE" +%Y)
  month=$(date -u -d "$DATE_OVERRIDE" +%m)
  day=$(date -u -d "$DATE_OVERRIDE" +%d)
else
  year=$(date -u +%Y)
  month=$(date -u +%m)
  day=$(date -u +%d)
fi
echo "Current Year  : $year"
echo "Current Month : $month"
echo "Current Day   : $day"

# create directory for current day
mkdir -p docs/$year/$month/$day

# retrieve data
./get-constituents.py

# copy files into daily folder (robust if no matches)
find docs/ -maxdepth 1 -type f -name '*.json' -exec cp -t "docs/$year/$month/$day" {} +
find docs/ -maxdepth 1 -type f -name '*.csv'  -exec cp -t "docs/$year/$month/$day" {} +

# update timestamp in index.html
./update-timestamp.sh
