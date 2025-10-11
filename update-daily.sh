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

# copy files into daily folder (robust if no matches)
find docs/ -maxdepth 1 -type f -name '*.json' -exec cp -t "docs/$year/$month/$day" {} +
find docs/ -maxdepth 1 -type f -name '*.csv'  -exec cp -t "docs/$year/$month/$day" {} +

# update timestamp in index.html
head -n -5 docs/index.html > docs/index.tmp.html
mv docs/index.tmp.html docs/index.html
./gen-footer.py >> docs/index.html
