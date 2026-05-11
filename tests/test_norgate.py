from quant.norgate import fetch_bars_from_cache, import_ascii_directory, import_metadata_directory, status, write_windows_bridge


def test_norgate_ascii_import(tmp_path, monkeypatch):
    import quant.norgate as norgate

    db = tmp_path / "norgate.sqlite"
    monkeypatch.setattr(norgate, "NORGATE_DB", db)
    export = tmp_path / "ascii" / "US"
    export.mkdir(parents=True)
    (export / "AAPL.csv").write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2024-01-02,100,101,99,100.5,1000000\n"
        "2024-01-03,101,102,100,101.5,1000001\n"
    )

    result = import_ascii_directory(export)
    assert result["rows_imported"] == 2
    bars = fetch_bars_from_cache("AAPL", "2024-01-01", "2024-01-10")
    assert bars[-1] == ("2024-01-03", 101.0, 102.0, 100.0, 101.5, 1000001)
    assert status()["ticker_count"] == 1


def test_norgate_flat_bridge_suffix_import(tmp_path, monkeypatch):
    import quant.norgate as norgate

    db = tmp_path / "norgate.sqlite"
    monkeypatch.setattr(norgate, "NORGATE_DB", db)
    export = tmp_path / "export" / "prices"
    export.mkdir(parents=True)
    (export / "AAPL.csv").write_text(
        "date,Open,High,Low,Close,Volume\n"
        "2024-01-02,100,101,99,100.5,1000000\n"
    )
    (export / "AAPL.ca.csv").write_text(
        "date,Open,High,Low,Close,Volume\n"
        "2024-01-02,20,21,19,20.5,100000\n"
    )

    result = import_ascii_directory(export)
    assert result["rows_imported"] == 2
    assert fetch_bars_from_cache("AAPL", "2024-01-01", "2024-01-10", market="US")
    assert fetch_bars_from_cache("AAPL.CA", "2024-01-01", "2024-01-10", market="CA")
    assert status()["ticker_count"] == 2


def test_windows_bridge_written(tmp_path):
    path = write_windows_bridge(tmp_path / "norgate_windows_export.py")
    text = open(path, encoding="utf-8").read()
    assert "norgatedata.price_timeseries" in text
    assert "security_master.csv" in text


def test_norgate_metadata_import(tmp_path, monkeypatch):
    import quant.norgate as norgate

    db = tmp_path / "norgate.sqlite"
    monkeypatch.setattr(norgate, "NORGATE_DB", db)
    meta = tmp_path / "export" / "metadata"
    meta.mkdir(parents=True)
    (meta / "security_master.csv").write_text(
        "symbol,assetid,name,domicile,currency,exchange,first_quoted_date,last_quoted_date,gics_sector\n"
        "AAPL,1,Apple Inc,US,USD,NASDAQ,1980-12-12,,Information Technology\n"
    )
    result = import_metadata_directory(tmp_path / "export")
    assert result["security_master_rows"] == 1
    assert status()["security_master_rows"] == 1
