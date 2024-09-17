# index-constituents

[![update-monthly](https://github.com/jcoffi/index-constituents/workflows/update-monthly/badge.svg)](https://github.com/jcoffi/index-constituents/actions?query=workflow:%22update-monthly%22)

Get the current and historical constituents of popular stock indices.
All symbols are consistent with those in [Yahoo Finance](https://finance.yahoo.com/).

## Supported indices


| Code      |  Name             |  Start   | Download                                                                                                                                                      |
|:----------|:------------------|:---------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| csi300    | CSI 300 (沪深300) | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi300.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi300.csv)       |
| csi500    | CSI 500 (中证500)   | 2024/01  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi500.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi500.csv)       |
| csi1000   | CSI 1000 (中证1000) | 2024/01  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi1000.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-csi1000.csv)     |
| sse       | SSE (上证综指)    | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-sse.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-sse.csv)             |
| szse      | SZSE (深证成指)   | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-szse.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-szse.csv)           |
| nasdaq100 | NASDAQ 100        | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-nasdaq100.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-nasdaq100.csv) |
| sp500     | S&P 500           | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-sp500.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-sp500.csv)         |
| dowjones  | Dow Jones         | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-dowjones.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-dowjones.csv)   |
| dax       | DAX               | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-dax.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-dax.csv)             |
| hsi       | HSI (恒生指数)    | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-hsi.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-hsi.csv)             |
| ftse100   | FTSE 100          | 2023/07  | [json](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-ftse100.json) / [csv](https://github.com/jcoffi/index-constituents/blob/main/docs/constituents-ftse100.csv)     |

## Usage
### Direct download
To get the current index constituents, use the links above. You probably have noticed the URLs have some pattern:

```sh
wget https://raw.githubusercontent.com/jcoffi/index-constituents/refs/heads/main/docs/constituents-$CODE.$FORMAT
```

### Use in your program
Using Python as an example:

```python
import pandas as pd

url = "https://raw.githubusercontent.com/jcoffi/index-constituents/refs/heads/main/docs/constituents-csi300.csv"
df = pd.read_csv(url)
```

### Build yourself
Check `requirements.txt`. Run:

```sh
./get-constituents.py
```

## Historical data
To get the historical index constituents, use the following URL:

```sh
https://github.com/jcoffi/index-constituents/blob/main/docs/$YYYY/$MM/constituents-$CODE.$FORMAT
```

By default we automatically update the data monthly (usually on the first day).
Historical data of a particular index is only available from the month we start to include it.

## Data source
* [乌龟量化](https://wglh.com/)
* [Slickcharts](https://www.slickcharts.com/)
* [Bloomberg](https://www.bloomberg.com/)

## Author
* Forked from original author: [yfiua](https://github.com/yfiua)
