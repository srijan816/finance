"""Export Norgate data from Windows for Quant Lab.

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
