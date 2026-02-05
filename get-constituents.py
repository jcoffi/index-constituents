#!/usr/bin/env python3
# coding: utf-8

import datetime
import io
import pandas as pd
import random  # Used for retry delay randomization in multiple places
import requests
import sys
import time

from selectorlib import Extractor

from fake_useragent import UserAgent
ua = UserAgent()
n_retries = 5

def get_constituents_from_csindex(url):
    # convert symbol from 'SYMBOL' to 'SYMBOL.SZ' or 'SYMBOL.SS'
    def convert_symbol_csindex(symbol):
        match symbol[0]:
            case '0' | '3':
                return symbol + '.SZ'
            case '6':
                return symbol + '.SS'
            case '4' | '8':
                return symbol + '.BJ'

        return symbol

    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    df = pd.read_excel(io.BytesIO(r.content), dtype=str)

    df = df[['成份券代码Constituent Code', '成份券名称Constituent Name']]
    df.columns = ['Symbol', 'Name']

    df['Symbol'] = df['Symbol'].apply(convert_symbol_csindex)

    return df

def get_constituents_from_slickcharts(url):
    selector_yml = '''
                    Symbol:
                        css: 'tr td:nth-of-type(3) a'
                        xpath: null
                        multiple: true
                        type: Text
                    Name:
                        css: 'div.col-lg-7 tr td:nth-of-type(2) a'
                        xpath: null
                        multiple: true
                        type: Text
                   '''

    e = Extractor.from_yaml_string(selector_yml)

    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers)

    data = e.extract(r.text)
    
    # Handle potential None values and array length mismatches
    symbols = data.get('Symbol') or []
    names = data.get('Name') or []
    
    # Handle mismatched lengths by taking the minimum
    min_length = min(len(symbols), len(names))
    symbols = symbols[:min_length]
    names = names[:min_length]
    
    df = pd.DataFrame({'Symbol': symbols, 'Name': names})

    return df

def get_constituents_from_nasdaqomx(index_symbol, suffix, trade_date=None, lookback_days=7):
    def normalize_symbol(symbol):
        symbol = str(symbol).strip().upper()
        symbol = symbol.replace(' ', '-')
        return symbol

    if trade_date is None:
        trade_date = datetime.date.today()

    last_exc = None
    for i in range(lookback_days + 1):
        date = trade_date - datetime.timedelta(days=i)
        url = (
            'https://indexes.nasdaqomx.com/Index/ExportWeightings/'
            f'{index_symbol}?tradeDate={date:%Y-%m-%d}T00:00:00.000&timeOfDay=EOD'
        )

        try:
            headers = { 'User-Agent' : ua.random }
            r = requests.get(url, headers=headers)
            r.raise_for_status()

            if not r.content:
                raise ValueError('Empty response from Nasdaq OMX export')

            df_raw = pd.read_excel(io.BytesIO(r.content), header=None)
            header_row = None
            for idx, row in df_raw.iterrows():
                if 'Company Name' in row.values and 'Security Symbol' in row.values:
                    header_row = int(idx)
                    break

            if header_row is None:
                raise ValueError('Header row not found in Nasdaq OMX export')

            df = pd.read_excel(io.BytesIO(r.content), header=header_row)

            if 'Security Symbol' not in df.columns or 'Company Name' not in df.columns:
                raise ValueError(f'Unexpected columns: {list(df.columns)}')

            df = df[['Security Symbol', 'Company Name']].copy()
            df.columns = ['Symbol', 'Name']
            df['Symbol'] = [normalize_symbol(x) + suffix for x in df['Symbol'].tolist()]

            if df.empty:
                raise ValueError('Empty constituents file')

            return df
        except Exception as e:
            last_exc = e
            continue

    if last_exc is None:
        raise RuntimeError('Failed to fetch Nasdaq OMX export')
    raise last_exc

# 沪深300
def get_constituents_csi300():
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000300cons.xls'
    return get_constituents_from_csindex(url)

# 中证500
def get_constituents_csi500():
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000500cons.xls'
    return get_constituents_from_csindex(url)

# 中证1000
def get_constituents_csi1000():
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000852cons.xls'
    return get_constituents_from_csindex(url)

# 上证指数
def get_constituents_sse():
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000001cons.xls'
    return get_constituents_from_csindex(url)

# 深证成指
def get_constituents_szse():
    url = 'https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xls&CATALOGID=1747_zs&ZSDM=399001'

    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    df = pd.read_excel(io.BytesIO(r.content), dtype=str)

    df = df[['证券代码', '证券简称']]
    df.columns = ['Symbol', 'Name']

    df['Symbol'] = df['Symbol'] + '.SZ'

    return df

# NASDAQ100
def get_constituents_nasdaq100():
    url = 'https://www.slickcharts.com/nasdaq100'
    return get_constituents_from_slickcharts(url)

# S&P500

# NIFTY 50
def get_constituents_nifty50():
    # Try official NIFTY indices site first, then fallback to NSE archive
    urls = [
        'https://niftyindices.com/IndexConstituent/ind_nifty50list.csv',
        'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
    ]

    last_exc = None
    for url in urls:
        try:
            headers = { 'User-Agent' : ua.random }
            r = requests.get(url, headers=headers)
            r.raise_for_status()  # Raise an exception for bad status codes
            df = pd.read_csv(io.StringIO(r.text), dtype=str)

            # Expected CSV columns (observed): Company Name,Industry,Symbol,Series,ISIN Code
            # Keep Symbol and Company Name
            if 'Symbol' in df.columns and 'Company Name' in df.columns:
                df = df[['Symbol', 'Company Name']].copy()
                df.columns = ['Symbol', 'Name']
            else:
                # Fallback: try to guess columns
                cols = [c for c in df.columns]
                # Try to find a column that looks like symbol/name
                sym_col = next((c for c in cols if c.lower() == 'symbol'), None)
                name_col = next((c for c in cols if 'company' in c.lower() or 'name' in c.lower()), None)
                if sym_col and name_col:
                    df = df[[sym_col, name_col]].copy()
                    df.columns = ['Symbol', 'Name']
                else:
                    raise ValueError(f'Unexpected CSV columns: {cols}')

            # Normalize symbols to use NSE suffix for Yahoo Finance compatibility
            df['Symbol'] = df['Symbol'].astype(str).str.upper().str.replace(r'\.NS$', '', regex=True) + '.NS'

            return df[['Symbol', 'Name']]
        except Exception as e:
            last_exc = e
            continue

    # If both attempts failed, raise the last exception
    if last_exc is None:
        raise RuntimeError('Failed to fetch NIFTY 50 constituents')
    raise last_exc

# OMXS30
def get_constituents_omxs30():
    return get_constituents_from_nasdaqomx('OMXS30', '.ST')

# NASDAQ Global Large Cap Index
def get_constituents_nqglci():
    return get_constituents_from_nasdaqomx('NQGLCI', '')

# NASDAQ Brazil Index
def get_constituents_nqbr():
    return get_constituents_from_nasdaqomx('NQBR', '.SA')

# NASDAQ Brazil Large Cap Index
def get_constituents_nqbrlc():
    return get_constituents_from_nasdaqomx('NQBRLC', '.SA')

# NASDAQ Canada Index
def get_constituents_nqca():
    return get_constituents_from_nasdaqomx('NQCA', '.TO')

# NASDAQ Canada Large Cap Index
def get_constituents_nqcalc():
    return get_constituents_from_nasdaqomx('NQCALC', '.TO')


# NASDAQ Mexico Index
def get_constituents_nqmx():
    return get_constituents_from_nasdaqomx('NQMX', '.MX')

# NASDAQ Mexico Large Cap Index
def get_constituents_nqmxlc():
    return get_constituents_from_nasdaqomx('NQMXLC', '.MX')


def get_constituents_sp500():
    url = 'https://www.slickcharts.com/sp500'
    return get_constituents_from_slickcharts(url)

# Dow Jones
def get_constituents_dowjones():
    url = 'https://www.slickcharts.com/dowjones'
    return get_constituents_from_slickcharts(url)

# DAX
def get_constituents_dax():
    # convert symbol from 'SYMBOL:GR' to 'SYMBOL.DE'
    def convert_symbol_dax(symbol):
        return symbol[:-3] + '.DE'

    selector_yml = '''
                    Symbol:
                        css: 'div.security-summary a.security-summary__ticker'
                        xpath: null
                        multiple: true
                        type: Text
                    Name:
                        css: 'div.security-summary a.security-summary__name'
                        xpath: null
                        multiple: true
                        type: Text
                   '''

    e = Extractor.from_yaml_string(selector_yml)

    url = 'https://www.bloomberg.com/quote/DAX:IND/members'
    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers)

    data = e.extract(r.text)
    symbols = data.get('Symbol') or []
    names = data.get('Name') or []

    min_length = min(len(symbols), len(names))
    symbols = symbols[:min_length]
    names = names[:min_length]

    if min_length == 0:
        raise ValueError('No DAX constituents extracted')

    df = pd.DataFrame({'Symbol': symbols, 'Name': names})
    df['Symbol'] = df['Symbol'].apply(convert_symbol_dax)

    return df

# Hang Seng Index
def get_constituents_hsi():
    # convert symbol from 'XX:HK' to '00XX.HK'
    def convert_symbol_hsi(symbol):
        return symbol.rjust(7, '0').replace(':', '.')

    selector_yml = '''
                    Symbol:
                        css: 'div.security-summary a.security-summary__ticker'
                        xpath: null
                        multiple: true
                        type: Text
                    Name:
                        css: 'div.security-summary a.security-summary__name'
                        xpath: null
                        multiple: true
                        type: Text
                   '''

    e = Extractor.from_yaml_string(selector_yml)

    url = 'https://www.bloomberg.com/quote/HSI:IND/members'
    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers)

    data = e.extract(r.text)
    symbols = data.get('Symbol') or []
    names = data.get('Name') or []

    min_length = min(len(symbols), len(names))
    symbols = symbols[:min_length]
    names = names[:min_length]

    if min_length == 0:
        raise ValueError('No HSI constituents extracted')

    df = pd.DataFrame({'Symbol': symbols, 'Name': names})
    df['Symbol'] = df['Symbol'].apply(convert_symbol_hsi)

    return df

# FTSE 100 (UKX)
def get_constituents_ftse100():
    # convert symbol from 'SYMBOL:LN' to 'SYMBOL.L'
    def convert_symbol_ftse100(symbol):
        return symbol.replace(':LN', '.L')

    selector_yml = '''
                    Symbol:
                        css: 'div.security-summary a.security-summary__ticker'
                        xpath: null
                        multiple: true
                        type: Text
                    Name:
                        css: 'div.security-summary a.security-summary__name'
                        xpath: null
                        multiple: true
                        type: Text
                   '''

    e = Extractor.from_yaml_string(selector_yml)

    url = 'https://www.bloomberg.com/quote/UKX:IND/members'
    headers = { 'User-Agent' : ua.random }
    r = requests.get(url, headers=headers)

    data = e.extract(r.text)
    symbols = data.get('Symbol') or []
    names = data.get('Name') or []

    min_length = min(len(symbols), len(names))
    symbols = symbols[:min_length]
    names = names[:min_length]

    if min_length == 0:
        raise ValueError('No FTSE 100 constituents extracted')

    df = pd.DataFrame({'Symbol': symbols, 'Name': names})
    df['Symbol'] = df['Symbol'].apply(convert_symbol_ftse100)

    return df

# main
if __name__ == '__main__':
    # track status
    status = 0

    # distribute requests to bloomberg to avoid overwhelming the server
    print('Fetching the constituents of DAX...')
    for i in range(n_retries):
        try:
            df = get_constituents_dax()
            df.to_csv('docs/constituents-dax.csv', index=False)
            df.to_json('docs/constituents-dax.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of DAX.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of CSI 300...')
    for i in range(n_retries):
        try:
            df = get_constituents_csi300()
            df.to_csv('docs/constituents-csi300.csv', index=False)
            df.to_json('docs/constituents-csi300.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of CSI 300.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of CSI 500...')
    for i in range(n_retries):
        try:
            df = get_constituents_csi500()
            df.to_csv('docs/constituents-csi500.csv', index=False)
            df.to_json('docs/constituents-csi500.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of CSI 500.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of CSI 1000...')
    for i in range(n_retries):
        try:
            df = get_constituents_csi1000()
            df.to_csv('docs/constituents-csi1000.csv', index=False)
            df.to_json('docs/constituents-csi1000.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of CSI 1000.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    time.sleep(random.paretovariate(2) * 25)  # Sleep for a while to avoid overwhelming the server
    print('Fetching the constituents of Hang Seng Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_hsi()
            df.to_csv('docs/constituents-hsi.csv', index=False)
            df.to_json('docs/constituents-hsi.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of Hang Seng Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of SSE...')
    for i in range(n_retries):
        try:
            df = get_constituents_sse()
            df.to_csv('docs/constituents-sse.csv', index=False)
            df.to_json('docs/constituents-sse.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of SSE.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of SZSE...')
    for i in range(n_retries):
        try:
            df = get_constituents_szse()
            df.to_csv('docs/constituents-szse.csv', index=False)
            df.to_json('docs/constituents-szse.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of SZSE.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of NASDAQ 100...')
    for i in range(n_retries):
        try:
            df = get_constituents_nasdaq100()
            df.to_csv('docs/constituents-nasdaq100.csv', index=False)
            df.to_json('docs/constituents-nasdaq100.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ 100.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of S&P 500...')
    for i in range(n_retries):
        try:
            df = get_constituents_sp500()
            df.to_csv('docs/constituents-sp500.csv', index=False)
            df.to_json('docs/constituents-sp500.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of S&P 500.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Fetching the constituents of Dow Jones...')
    for i in range(n_retries):
        try:
            df = get_constituents_dowjones()
            df.to_csv('docs/constituents-dowjones.csv', index=False)
            df.to_json('docs/constituents-dowjones.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of Dow Jones.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    time.sleep(random.paretovariate(2) * 25)  # Sleep for a while to avoid overwhelming the server
    print('Fetching the constituents of FTSE 100...')
    for i in range(n_retries):
        try:
            df = get_constituents_ftse100()
            df.to_csv('docs/constituents-ftse100.csv', index=False)
            df.to_json('docs/constituents-ftse100.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of FTSE 100.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NIFTY 50
    print('Fetching the constituents of NIFTY 50...')
    for i in range(n_retries):
        try:
            df = get_constituents_nifty50()
            df.to_csv('docs/constituents-nifty50.csv', index=False)
            df.to_json('docs/constituents-nifty50.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NIFTY 50.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # OMXS30
    print('Fetching the constituents of OMXS30...')
    for i in range(n_retries):
        try:
            df = get_constituents_omxs30()
            df.to_csv('docs/constituents-omxs30.csv', index=False)
            df.to_json('docs/constituents-omxs30.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of OMXS30.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Global Large Cap Index
    print('Fetching the constituents of NASDAQ Global Large Cap Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqglci()
            df.to_csv('docs/constituents-nqglci.csv', index=False)
            df.to_json('docs/constituents-nqglci.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Global Large Cap Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Brazil Index
    print('Fetching the constituents of NASDAQ Brazil Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqbr()
            df.to_csv('docs/constituents-nqbr.csv', index=False)
            df.to_json('docs/constituents-nqbr.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Brazil Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Brazil Large Cap Index
    print('Fetching the constituents of NASDAQ Brazil Large Cap Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqbrlc()
            df.to_csv('docs/constituents-nqbrlc.csv', index=False)
            df.to_json('docs/constituents-nqbrlc.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Brazil Large Cap Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Canada Index
    print('Fetching the constituents of NASDAQ Canada Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqca()
            df.to_csv('docs/constituents-nqca.csv', index=False)
            df.to_json('docs/constituents-nqca.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Canada Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Canada Large Cap Index
    print('Fetching the constituents of NASDAQ Canada Large Cap Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqcalc()
            df.to_csv('docs/constituents-nqcalc.csv', index=False)
            df.to_json('docs/constituents-nqcalc.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Canada Large Cap Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Mexico Index
    print('Fetching the constituents of NASDAQ Mexico Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqmx()
            df.to_csv('docs/constituents-nqmx.csv', index=False)
            df.to_json('docs/constituents-nqmx.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Mexico Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    # NASDAQ Mexico Large Cap Index
    print('Fetching the constituents of NASDAQ Mexico Large Cap Index...')
    for i in range(n_retries):
        try:
            df = get_constituents_nqmxlc()
            df.to_csv('docs/constituents-nqmxlc.csv', index=False)
            df.to_json('docs/constituents-nqmxlc.json', orient='records')
        except Exception as e:
            print(f'Attempt {i+1} failed: {e}')
            if i == n_retries - 1:
                status = 1
                print('Failed to fetch the constituents of NASDAQ Mexico Large Cap Index.')
            else:
                time.sleep(random.paretovariate(2) * 5)
            continue
        else:
            break

    print('Done.')

    sys.exit(status)
