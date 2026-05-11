"""Norgate Data import helpers.

The full Norgate Python API is Windows-only because it requires the Norgate
Data Updater application to be installed and running. This module supports the
Mac-compatible path: import ASCII/CSV exports into a local SQLite cache that the
rest of Quant Lab can read.
"""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
NORGATE_DIR = DATA_DIR / "norgate"
NORGATE_ASCII_DIR = NORGATE_DIR / "ascii"
NORGATE_DB = NORGATE_DIR / "norgate.sqlite"


@dataclass(frozen=True)
class ImportResult:
    source_path: str
    ticker: str
    market: str
    rows: int
    first_date: str
    last_date: str


def norgate_db_path() -> Path:
    NORGATE_DIR.mkdir(parents=True, exist_ok=True)
    return NORGATE_DB


def import_ascii_directory(path: str | Path, market: str = "", overwrite: bool = True) -> dict:
    """Import Norgate ASCII/CSV exports from a directory tree."""
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Norgate export directory not found: {root}")
    files = sorted(
        item for item in root.rglob("*")
        if item.is_file() and item.suffix.lower() in {".csv", ".txt", ".asc"}
    )
    results = []
    conn = _connect()
    try:
        _ensure_schema(conn)
        for idx, file_path in enumerate(files, start=1):
            result = _import_ascii_file_with_conn(
                file_path,
                conn,
                market=market or _market_from_path(file_path, root),
                overwrite=overwrite,
            )
            if result.rows:
                results.append(result)
            if idx % 500 == 0:
                conn.commit()
        conn.commit()
    finally:
        conn.close()
    return {
        "source": str(root),
        "market": market or "mixed_or_inferred",
        "files_seen": len(files),
        "files_imported": len(results),
        "rows_imported": sum(item.rows for item in results),
        "tickers": sorted({item.ticker for item in results}),
        "results": [item.__dict__ for item in results],
    }


def import_metadata_directory(path: str | Path, overwrite: bool = True) -> dict:
    """Import metadata exported by the Windows bridge."""
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Norgate metadata directory not found: {root}")
    conn = _connect()
    imported_security_master = 0
    imported_constituents = 0
    try:
        _ensure_schema(conn)
        security_master = next(iter(sorted(root.rglob("security_master.csv"))), None)
        if security_master is not None:
            if overwrite:
                conn.execute("DELETE FROM norgate_security_master")
            for row in csv.DictReader(open(security_master, newline="", encoding="utf-8-sig")):
                symbol = _normalize_ticker(row.get("symbol", ""))
                if not symbol:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO norgate_security_master (
                        symbol, assetid, name, domicile, currency, exchange,
                        first_quoted_date, last_quoted_date, gics_sector, source_file, imported_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        row.get("assetid", ""),
                        row.get("name", ""),
                        row.get("domicile", ""),
                        row.get("currency", ""),
                        row.get("exchange", ""),
                        row.get("first_quoted_date", ""),
                        row.get("last_quoted_date", ""),
                        row.get("gics_sector", ""),
                        str(security_master),
                        _utc_now(),
                    ),
                )
                imported_security_master += 1

        constituent_files = sorted((root / "constituents").glob("*.csv")) if (root / "constituents").exists() else []
        if overwrite and constituent_files:
            conn.execute("DELETE FROM norgate_constituents")
        for file_path in constituent_files:
            index_name, symbol = _constituent_filename_parts(file_path)
            for row in csv.DictReader(open(file_path, newline="", encoding="utf-8-sig")):
                date_value = row.get("date") or row.get("Date") or ""
                if not date_value:
                    continue
                member_value = _first_numeric_value(row)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO norgate_constituents (
                        index_name, ticker, date, is_member, source_file, imported_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (index_name, symbol, _parse_date(date_value), int(member_value), str(file_path), _utc_now()),
                )
                imported_constituents += 1
        conn.commit()
    finally:
        conn.close()
    return {
        "source": str(root),
        "security_master_rows": imported_security_master,
        "constituent_rows": imported_constituents,
        "limitations": [
            "Metadata quality depends on the Windows bridge export arguments and your Norgate subscription level.",
            "Constituent files are imported only if the bridge exported an --index timeseries.",
        ],
    }


def import_ascii_file(path: str | Path, market: str = "", overwrite: bool = True) -> ImportResult:
    """Import one exported OHLCV file."""
    file_path = Path(path).expanduser()
    conn = _connect()
    try:
        _ensure_schema(conn)
        result = _import_ascii_file_with_conn(file_path, conn, market=market, overwrite=overwrite)
        conn.commit()
        return result
    finally:
        conn.close()


def _import_ascii_file_with_conn(
    file_path: Path,
    conn: sqlite3.Connection,
    market: str = "",
    overwrite: bool = True,
) -> ImportResult:
    rows = _read_ascii_rows(file_path)
    ticker = _ticker_from_rows_or_filename(rows, file_path)
    market = (market or _market_from_path(file_path, file_path.parent)).upper() or "UNKNOWN"
    if overwrite:
        conn.execute("DELETE FROM norgate_bars WHERE ticker = ? AND market = ?", (ticker, market))
    inserted = 0
    first_date = ""
    last_date = ""
    imported_at = _utc_now()
    for row in rows:
        date_value = row["date"]
        first_date = first_date or date_value
        last_date = date_value
        conn.execute(
            """
            INSERT OR REPLACE INTO norgate_bars (
                ticker, market, date, open, high, low, close, volume, source_file, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                market,
                date_value,
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                str(file_path),
                imported_at,
            ),
        )
        inserted += 1
    return ImportResult(str(file_path), ticker, market, inserted, first_date, last_date)


def fetch_bars_from_cache(ticker: str, start: str, end: str, market: str = "") -> list[tuple]:
    """Fetch imported Norgate OHLCV bars."""
    ticker = _normalize_ticker(ticker)
    conn = _connect()
    try:
        _ensure_schema(conn)
        params: list = [ticker, start, end]
        market_clause = ""
        if market:
            market_clause = " AND market = ?"
            params.append(market.upper())
        rows = conn.execute(
            f"""
            SELECT date, open, high, low, close, volume
            FROM norgate_bars
            WHERE ticker = ? AND date >= ? AND date <= ?{market_clause}
            ORDER BY date
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [(row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"])) for row in rows]


def status() -> dict:
    """Return local Norgate import status."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT ticker, market, COUNT(*) AS rows, MIN(date) AS first_date, MAX(date) AS last_date
            FROM norgate_bars
            GROUP BY ticker, market
            ORDER BY market, ticker
            """
        ).fetchall()
        security_master_count = conn.execute("SELECT COUNT(*) AS n FROM norgate_security_master").fetchone()["n"]
        constituent_count = conn.execute("SELECT COUNT(*) AS n FROM norgate_constituents").fetchone()["n"]
    finally:
        conn.close()
    items = [dict(row) for row in rows]
    return {
        "db_path": str(norgate_db_path()),
        "ascii_import_dir": str(NORGATE_ASCII_DIR),
        "ticker_count": len({row["ticker"] for row in items}),
        "market_count": len({row["market"] for row in items}),
        "rows": sum(int(row["rows"]) for row in items),
        "security_master_rows": int(security_master_count),
        "constituent_rows": int(constituent_count),
        "items": items,
        "limitations": [
            "Mac ASCII imports provide daily OHLCV bars only.",
            "Historical index membership, delisted/security-master metadata, and fundamentals require Norgate's Windows API/export bridge.",
            "Set QUANT_DATA_SOURCE=norgate after importing files to make Quant Lab use this cache.",
        ],
    }


def windows_bridge_script() -> str:
    """Return a Windows-side export script for full Norgate Python API users."""
    return r'''"""Export Norgate data from Windows for Quant Lab.

Run this on the Windows machine/VM where Norgate Data Updater is installed and
logged in. Example:

    python norgate_windows_export.py --symbols AAPL,MSFT,NVDA --out C:/quant_lab_norgate_export
    python norgate_windows_export.py --databases "US Equities,US Equities Delisted,CA Equities,AU Equities" --out C:/quant_lab_norgate_export

Then copy the output folder to your Mac and run:

    quant norgate import-ascii --path /path/to/quant_lab_norgate_export/prices
"""
import csv
import argparse
from pathlib import Path

import norgatedata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="", help="Comma-separated Norgate symbols")
    parser.add_argument("--databases", default="", help="Comma-separated Norgate database names")
    parser.add_argument("--watchlists", default="", help="Comma-separated Norgate watchlist names")
    parser.add_argument("--index", default="", help="Optional index name for constituent timeseries, e.g. S&P 500")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--start", default="1900-01-01")
    parser.add_argument("--list-only", action="store_true", help="Only export available database/watchlist names")
    parser.add_argument("--skip-prices", action="store_true", help="Export metadata/security master but skip price CSVs")
    parser.add_argument("--limit", type=int, default=0, help="Optional max symbols for a test export")
    args = parser.parse_args()
    out = Path(args.out)
    price_dir = out / "prices"
    price_dir.mkdir(parents=True, exist_ok=True)

    symbols = set(s.strip() for s in args.symbols.split(",") if s.strip())

    metadata_dir = out / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    with open(metadata_dir / "available_databases.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["database"])
        for database in norgatedata.databases():
            writer.writerow([database])
    with open(metadata_dir / "available_watchlists.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["watchlist"])
        for watchlist in norgatedata.watchlists():
            writer.writerow([watchlist])

    if args.list_only:
        print(f"Wrote available database/watchlist names to {metadata_dir}")
        return

    for databasename in [s.strip() for s in args.databases.split(",") if s.strip()]:
        securities = norgatedata.database(databasename)
        with open(metadata_dir / f"database_{safe_name(databasename)}.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["database", "symbol", "assetid", "name"])
            for item in securities:
                symbol, assetid, name = unpack_security(item)
                writer.writerow([databasename, symbol, assetid, name])
                symbols.add(symbol)

    for watchlistname in [s.strip() for s in args.watchlists.split(",") if s.strip()]:
        securities = norgatedata.watchlist(watchlistname)
        with open(metadata_dir / f"watchlist_{safe_name(watchlistname)}.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["watchlist", "symbol", "assetid", "name"])
            for item in securities:
                symbol, assetid, name = unpack_security(item)
                writer.writerow([watchlistname, symbol, assetid, name])
                symbols.add(symbol)

    sorted_symbols = sorted(symbols)
    if args.limit and args.limit > 0:
        sorted_symbols = sorted_symbols[:args.limit]

    with open(metadata_dir / "security_master.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "symbol", "assetid", "name", "domicile", "currency", "exchange",
            "first_quoted_date", "last_quoted_date", "gics_sector",
        ])
        for symbol in sorted_symbols:
            writer.writerow([
                symbol,
                safe_call(norgatedata.assetid, symbol),
                safe_call(norgatedata.security_name, symbol),
                safe_call(norgatedata.domicile, symbol),
                safe_call(norgatedata.currency, symbol),
                safe_call(norgatedata.exchange_name, symbol),
                safe_call(norgatedata.first_quoted_date, symbol),
                safe_call(norgatedata.last_quoted_date, symbol),
                safe_call(norgatedata.classification_at_level, symbol, "GICS", "Name", 1),
            ])

    if not args.skip_prices:
        error_dir = out / "errors"
        error_dir.mkdir(parents=True, exist_ok=True)
        with open(error_dir / "price_export_errors.csv", "w", newline="", encoding="utf-8") as error_handle:
            error_writer = csv.writer(error_handle)
            error_writer.writerow(["symbol", "stage", "error"])
            for idx, symbol in enumerate(sorted_symbols, start=1):
                print(f"[{idx}/{len(sorted_symbols)}] exporting {symbol}")
                try:
                    df = norgatedata.price_timeseries(
                        symbol,
                        stock_price_adjustment_setting=norgatedata.StockPriceAdjustmentType.TOTALRETURN,
                        padding_setting=norgatedata.PaddingType.NONE,
                        start_date=args.start,
                        timeseriesformat="pandas-dataframe",
                    )
                    df = df.reset_index()
                    df.rename(columns={df.columns[0]: "date"}, inplace=True)
                    keep = ["date", "Open", "High", "Low", "Close", "Volume"]
                    df[keep].to_csv(price_dir / f"{symbol}.csv", index=False)
                except Exception as exc:
                    error_writer.writerow([symbol, "price", str(exc)])
                    continue

                if args.index:
                    try:
                        idx_df = norgatedata.index_constituent_timeseries(
                            symbol,
                            args.index,
                            padding_setting=norgatedata.PaddingType.NONE,
                            start_date=args.start,
                            timeseriesformat="pandas-dataframe",
                        ).reset_index()
                        idx_df.rename(columns={idx_df.columns[0]: "date"}, inplace=True)
                        constituents_dir = out / "constituents"
                        constituents_dir.mkdir(parents=True, exist_ok=True)
                        idx_df.to_csv(constituents_dir / f"{safe_name(args.index)}_{symbol}.csv", index=False)
                    except Exception as exc:
                        error_writer.writerow([symbol, "constituent", str(exc)])

    with open(out / "README.txt", "w", encoding="utf-8") as handle:
        handle.write("Norgate export for Quant Lab. Copy this folder to Mac and import prices/*.csv. Metadata lives under metadata/.\n")


def unpack_security(item):
    if isinstance(item, dict):
        return item.get("symbol") or item.get("Symbol"), item.get("assetid") or item.get("AssetId"), item.get("name") or item.get("Name")
    values = list(item) if isinstance(item, (tuple, list)) else [item]
    symbol = values[0] if len(values) > 0 else ""
    assetid = values[1] if len(values) > 1 else ""
    name = values[2] if len(values) > 2 else ""
    return symbol, assetid, name


def safe_call(func, *args):
    try:
        value = func(*args)
        return "" if value is None else value
    except Exception:
        return ""


def safe_name(value):
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")


if __name__ == "__main__":
    main()
'''


def write_windows_bridge(path: str | Path) -> str:
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(windows_bridge_script(), encoding="utf-8")
    return str(output)


def _read_ascii_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t| ") if sample.strip() else csv.excel
    has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
    raw_rows = list(csv.reader(text.splitlines(), dialect))
    if not raw_rows:
        return []
    if has_header:
        header = [_normalize_column(col) for col in raw_rows[0]]
        data_rows = raw_rows[1:]
    else:
        width = len(raw_rows[0])
        header = _default_header(width)
        data_rows = raw_rows
    parsed = []
    for raw in data_rows:
        if not raw or len(raw) < 5:
            continue
        row = {header[idx]: value.strip() for idx, value in enumerate(raw) if idx < len(header)}
        try:
            parsed.append({
                "ticker": _normalize_ticker(row.get("ticker", "")),
                "date": _parse_date(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(float(row.get("volume") or 0)),
            })
        except (KeyError, ValueError):
            continue
    return sorted(parsed, key=lambda item: item["date"])


def _default_header(width: int) -> list[str]:
    if width >= 7:
        return ["ticker", "date", "open", "high", "low", "close", "volume"] + [f"extra_{i}" for i in range(width - 7)]
    return ["date", "open", "high", "low", "close", "volume"][:width]


def _normalize_column(value: str) -> str:
    text = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "datetime": "date",
        "time": "date",
        "symbol": "ticker",
        "security": "ticker",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "last": "close",
        "adj_close": "close",
        "adjusted_close": "close",
        "v": "volume",
        "vol": "volume",
    }
    return aliases.get(text, text)


def _parse_date(value: str) -> str:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return datetime.fromisoformat(text[:10]).date().isoformat()


def _ticker_from_rows_or_filename(rows: list[dict], path: Path) -> str:
    for row in rows:
        if row.get("ticker"):
            return _normalize_ticker(row["ticker"])
    return _normalize_ticker(path.stem)


def _market_from_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = [part.upper() for part in rel.parts]
    for candidate in parts:
        if candidate in {"US", "USA", "UNITED_STATES"}:
            return "US"
        if candidate in {"CA", "CAN", "CANADA"}:
            return "CA"
        if candidate in {"AU", "AUS", "AUSTRALIA"}:
            return "AU"
    filename_parts = path.stem.lower().split(".")
    if filename_parts[-1:] == ["ca"]:
        return "CA"
    if filename_parts[-1:] == ["au"]:
        return "AU"
    if path.parent.name.lower() == "prices":
        return "US"
    return ""


def _normalize_ticker(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def _connect() -> sqlite3.Connection:
    path = norgate_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS norgate_bars (
            ticker TEXT NOT NULL,
            market TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            PRIMARY KEY (ticker, market, date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norgate_bars_lookup ON norgate_bars(ticker, date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS norgate_security_master (
            symbol TEXT PRIMARY KEY,
            assetid TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            domicile TEXT NOT NULL DEFAULT '',
            currency TEXT NOT NULL DEFAULT '',
            exchange TEXT NOT NULL DEFAULT '',
            first_quoted_date TEXT NOT NULL DEFAULT '',
            last_quoted_date TEXT NOT NULL DEFAULT '',
            gics_sector TEXT NOT NULL DEFAULT '',
            source_file TEXT NOT NULL,
            imported_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS norgate_constituents (
            index_name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            is_member INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            PRIMARY KEY (index_name, ticker, date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norgate_constituents_lookup ON norgate_constituents(index_name, date)")
    conn.commit()


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _constituent_filename_parts(path: Path) -> tuple[str, str]:
    stem = path.stem
    if "_" not in stem:
        return stem, stem
    left, right = stem.rsplit("_", 1)
    return left, _normalize_ticker(right)


def _first_numeric_value(row: dict) -> int:
    for key, value in row.items():
        if key.lower() == "date":
            continue
        try:
            return 1 if float(value) > 0 else 0
        except (TypeError, ValueError):
            continue
    return 0
