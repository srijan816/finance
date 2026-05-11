from datetime import date, timedelta


def _bars(ticker, start_price=100.0, n=180, drift=0.001, start=date(2024, 1, 1)):
    rows = []
    price = start_price
    for idx in range(n):
        price *= 1 + drift
        rows.append((ticker, "US", (start + timedelta(days=idx)).isoformat(), price, price, price, price, 1_000_000))
    return rows


def test_norgate_survivorship_sim_uses_delisted_universe(tmp_path, monkeypatch):
    import quant.norgate as norgate
    from quant.norgate import _connect, _ensure_schema
    from quant.norgate_simulator import simulate_norgate_survivorship

    db = tmp_path / "norgate.sqlite"
    monkeypatch.setattr(norgate, "NORGATE_DB", db)
    conn = _connect()
    _ensure_schema(conn)
    securities = [
        ("AAA", "AAA Corp Common", "US", "USD", "NYSE", "2024-01-01", "", "Technology", "test", "now"),
        ("BBB", "BBB Corp Common", "US", "USD", "NYSE", "2024-01-01", "2024-04-30", "Technology", "test", "now"),
        ("CCC", "CCC ETF", "US", "USD", "NYSE Arca", "2024-01-01", "", "", "test", "now"),
        ("SPY", "SPDR S&P 500 ETF", "US", "USD", "NYSE Arca", "2024-01-01", "", "", "test", "now"),
    ]
    conn.executemany(
        """
        INSERT INTO norgate_security_master (
            symbol, name, domicile, currency, exchange, first_quoted_date,
            last_quoted_date, gics_sector, source_file, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        securities,
    )
    all_rows = (
        _bars("AAA", 100, drift=0.002)
        + _bars("BBB", 100, n=121, drift=0.004)
        + _bars("CCC", 100, drift=0.01)
        + _bars("SPY", 100, drift=0.001)
    )
    conn.executemany(
        """
        INSERT INTO norgate_bars (
            ticker, market, date, open, high, low, close, volume, source_file, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'test', 'now')
        """,
        all_rows,
    )
    conn.commit()
    conn.close()

    result = simulate_norgate_survivorship(
        start="2024-01-01",
        end="2024-06-20",
        initial_capital=10_000,
        lookback=20,
        min_history=30,
        rebalance_step=21,
        max_positions=2,
        min_dollar_volume=1,
    )
    assert "error" not in result
    assert result["n_securities"] == 2
    assert result["n_delisted_or_ended_securities"] == 1
    selected = {row["ticker"] for rebalance in result["rebalances"] for row in rebalance["selected"]}
    assert "CCC" not in selected
    assert "BBB" in selected
