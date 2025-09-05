# Index Constituents Repository - Copilot Instructions

## Repository Overview
This is a Python-based web scraping project that collects and maintains current and historical stock index constituent data. It fetches data from multiple external sources (CSI Index, Slickcharts, Bloomberg) and publishes CSV/JSON files via GitHub Pages. The repository tracks constituents for 11 major global indices including S&P 500, NASDAQ 100, CSI 300, DAX, and others.

**Key characteristics:**
- **Size:** Small repository (~715 lines of Python code across 3 scripts)
- **Language:** Python 3.12+  
- **Type:** Data collection/web scraping automation
- **Output:** CSV and JSON files served via GitHub Pages
- **Automation:** Daily updates via GitHub Actions

## Build and Validation Process

### Prerequisites
- Python 3.12 or higher
- Internet connectivity for web scraping

### Setup and Dependencies
**Always run dependency installation before any other operations:**
```bash
pip install -r requirements.txt
```

Dependencies include: pandas>=2.0.0, requests>=2.25.1, selectorlib>=0.16.0, tabulate>=0.9.0, xlrd>=2.0.1, fake-useragent>=2.2.0, openpyxl>=3.1.2

### Running the Main Script
**Primary command to fetch all index data:**
```bash
./get-constituents.py
```

**Important timing considerations:**
- Script includes deliberate delays (up to 25 seconds) to avoid overwhelming external servers
- Total execution time: 2-5 minutes depending on network conditions
- Uses retry logic with random delays for Bloomberg-sourced data (DAX, HSI, FTSE 100)
- **Always allow at least 5 minutes timeout when running programmatically**

### Daily Update Process
```bash
./update-daily.sh
```
This script:
1. Creates timestamped directories under docs/YYYY/MM/DD/
2. Runs get-constituents.py to fetch latest data
3. Copies generated files to both docs/ root and daily snapshot directories

### Validation Steps
**To verify the build process works:**
1. Check that get-constituents.py and update-daily.sh are executable
2. Run `pip install -r requirements.txt`  
3. Execute `./get-constituents.py` and verify CSV/JSON files are generated in docs/
4. Check that all 11 indices have corresponding files (csi300, csi500, csi1000, sse, szse, nasdaq100, sp500, dowjones, dax, hsi, ftse100)

**Common issues and workarounds:**
- **Network timeouts:** The script has built-in retry logic; if it fails, simply re-run
- **Permission errors:** Ensure scripts are executable with `chmod +x *.py *.sh`
- **Missing docs/ directory:** Script will create it automatically
- **Partial failures:** Script continues even if individual indices fail; check console output

## Project Layout and Architecture

### Key Files and Structure
```
/
├── get-constituents.py          # Main data collection script (325 lines)
├── update-daily.sh             # Daily automation wrapper script  
├── gen-supported-indices-md.py # README table generator (24 lines)
├── requirements.txt            # Python dependencies
├── supported-indices.csv      # Index metadata configuration
├── docs/                      # Generated output files (GitHub Pages)
│   ├── constituents-*.csv     # Current data in CSV format
│   ├── constituents-*.json    # Current data in JSON format  
│   └── YYYY/MM/DD/           # Historical snapshots
├── .github/workflows/
│   └── update-daily.yml      # Daily automation (22:00 UTC)
└── scripts/
    └── import_historical_snapshots.py  # Historical data import utility
```

### Main Script Architecture (get-constituents.py)
**Core functions for each index:**
- `get_constituents_csi300/500/1000()` - Chinese indices from CSI Excel files
- `get_constituents_sse/szse()` - Chinese exchanges from Excel files  
- `get_constituents_nasdaq100/sp500/dowjones()` - US indices from Slickcharts HTML
- `get_constituents_dax/hsi/ftse100()` - International indices from Bloomberg HTML (with retry logic)

**Data processing patterns:**
- Symbol normalization (e.g., Chinese symbols get .SZ/.SS/.BJ suffixes)
- pandas DataFrame manipulation for CSV/JSON output
- Error handling with try/catch blocks per index
- Rate limiting with `time.sleep()` and random delays

### GitHub Actions Workflow
**Automation:** `.github/workflows/update-daily.yml`
- **Schedule:** Daily at 22:00 UTC via cron
- **Manual trigger:** workflow_dispatch
- **Process:** pip install → ./update-daily.sh → auto-commit changes
- **Permissions:** Requires contents:write for git operations

### Validation Pipeline
**No automated tests exist.** To validate changes:
1. Run get-constituents.py and check console output for errors
2. Verify expected files are generated in docs/ directory
3. Check file contents are valid CSV/JSON with reasonable data
4. For workflow changes, test with workflow_dispatch trigger

### Dependencies and External Services
**Critical external dependencies:**
- **CSI Index (csindex.com.cn):** Excel files for Chinese indices
- **Slickcharts (slickcharts.com):** HTML tables for US indices  
- **Bloomberg (bloomberg.com):** HTML pages for international indices
- **Network reliability:** Script designed to handle failures gracefully

### Configuration Files
- **No linting configs:** No .flake8, .pylintrc, or similar files detected
- **supported-indices.csv:** Master list of tracked indices with start dates
- **requirements.txt:** Locked dependency versions for reproducibility

## Key Development Guidelines

### Making Changes
- **Scripts use web scraping:** Changes to parsing logic may break due to external site changes
- **Test against real data sources:** No mock data available
- **Timing sensitive:** Respect rate limiting and don't remove sleep statements
- **Output format:** Maintain CSV/JSON schema compatibility for existing consumers

### Common Tasks
**Adding a new index:** 
1. Add entry to supported-indices.csv
2. Implement get_constituents_NEWINDEX() function  
3. Add fetch logic to main execution block
4. Update gen-supported-indices-md.py if needed

**Modifying data sources:**
1. Update URL/selector logic in respective function
2. Test symbol conversion logic for that market
3. Verify output format matches existing pattern

### Files to Exclude from Changes
- **docs/\*\*:** Generated files, managed by automation
- **\_\_pycache\_\_/\*\*:** Python bytecode (in .gitignore)

**Trust these instructions and only search the codebase if information is incomplete or found to be incorrect.**