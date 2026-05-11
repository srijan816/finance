"""Tests for quant/universe.py"""
from quant.universe import UniverseMember, get_universe, load_universe_csv, normalize_symbol


def test_universe_csv_point_in_time(tmp_path):
    path = tmp_path / "u.csv"
    path.write_text(
        "symbol,start_date,end_date,name,sector,source\n"
        "AAA,2020-01-01,,AAA Corp,Tech,test\n"
        "BBB,2022-01-01,,BBB Corp,Tech,test\n"
        "CCC,2019-01-01,2020-12-31,CCC Corp,Tech,test\n"
    )
    records = load_universe_csv(path)
    active = sorted(member.symbol for member in records if member.active_on(__import__("datetime").date(2021, 1, 1)))
    assert active == ["AAA"]


def test_normalize_symbol_for_yfinance():
    assert normalize_symbol("BRK.B") == "BRK-B"
