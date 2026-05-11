"""Data layer: yfinance/Norgate + SQLite cache."""
import yfinance as yf
import os, sqlite3, hashlib
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def cache_db():
    return str(DATA_DIR / "quotes.db")

def _get_cache_key(ticker: str, start: str, end: str) -> str:
    return hashlib.sha256(f"{ticker}{start}{end}".encode()).hexdigest()[:16]

def _init_cache():
    conn = sqlite3.connect(cache_db())
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS bars
        (key TEXT, ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER,
         PRIMARY KEY (key, date))""")
    conn.commit()
    return conn

def get_bars(ticker: str, start: str, end: str, force_refresh: bool = False):
    """Get OHLCV bars from yfinance with SQLite caching. Returns list of (date, open, high, low, close, volume)."""
    if os.getenv("QUANT_DATA_SOURCE", "").strip().lower() == "norgate":
        return fetch_bars(ticker, start, end)

    cache_key = _get_cache_key(ticker, start, end)

    conn = _init_cache()
    cur = conn.cursor()

    if not force_refresh:
        cur.execute("SELECT date,open,high,low,close,volume FROM bars WHERE key=? ORDER BY date", (cache_key,))
        rows = cur.fetchall()
        if len(rows) > 0:
            conn.close()
            return list(rows)

    # Fetch fresh from yfinance
    data = yf.download(ticker, start=start, end=end, progress=False)
    rows = []
    for idx, row in data.iterrows():
        date_str = str(idx.date())
        o = float(row['Open'].iloc[0]) if hasattr(row['Open'], 'iloc') else float(row['Open'])
        h = float(row['High'].iloc[0]) if hasattr(row['High'], 'iloc') else float(row['High'])
        l = float(row['Low'].iloc[0]) if hasattr(row['Low'], 'iloc') else float(row['Low'])
        c = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
        v = int(row['Volume'].iloc[0]) if hasattr(row['Volume'], 'iloc') else int(row['Volume'])
        rows.append((date_str, o, h, l, c, v))
        cur.execute("INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?)",
            (cache_key, ticker, date_str, o, h, l, c, v))

    conn.commit()
    conn.close()
    return rows

def fetch_bars(ticker: str, start: str, end: str):
    """Fetch OHLCV bars directly from the configured data source."""
    if os.getenv("QUANT_DATA_SOURCE", "").strip().lower() == "norgate":
        from quant.norgate import fetch_bars_from_cache

        bars = fetch_bars_from_cache(ticker, start, end, market=os.getenv("QUANT_NORGATE_MARKET", ""))
        if not bars:
            raise ValueError(
                f"No imported Norgate bars for {ticker} between {start} and {end}. "
                "Run `quant norgate import-ascii --path <export-folder>` or unset QUANT_DATA_SOURCE."
            )
        return bars

    data = yf.download(ticker, start=start, end=end, progress=False)
    bars = []
    for idx, row in data.iterrows():
        o = float(row['Open'].iloc[0]) if hasattr(row['Open'], 'iloc') else float(row['Open'])
        h = float(row['High'].iloc[0]) if hasattr(row['High'], 'iloc') else float(row['High'])
        l = float(row['Low'].iloc[0]) if hasattr(row['Low'], 'iloc') else float(row['Low'])
        c = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
        v = int(row['Volume'].iloc[0]) if hasattr(row['Volume'], 'iloc') else int(row['Volume'])
        bars.append((str(idx.date()), o, h, l, c, v))
    return bars
