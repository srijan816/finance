"""Point-in-time universe membership and provenance."""
from __future__ import annotations

import csv
from io import StringIO
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Sequence

UNIVERSE_DIR = Path(__file__).parent.parent / "data" / "universes"
WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    start_date: date
    end_date: date | None = None
    name: str = ""
    sector: str = ""
    source: str = ""

    def active_on(self, as_of: date) -> bool:
        return self.start_date <= as_of and (self.end_date is None or as_of <= self.end_date)


def get_universe(name: str, as_of: str | date) -> dict:
    """Return universe members and data quality metadata for a historical date."""
    as_of_date = parse_date(as_of)
    if name in {"sp500_wikipedia", "wikipedia_sp500"}:
        members, meta = wikipedia_sp500_members(as_of_date)
        return {"name": "sp500_wikipedia", "as_of": as_of_date.isoformat(), "members": members, "metadata": meta}

    path = UNIVERSE_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    records = load_universe_csv(path)
    return {
        "name": name,
        "as_of": as_of_date.isoformat(),
        "members": sorted(member.symbol for member in records if member.active_on(as_of_date)),
        "metadata": {
            "source": str(path),
            "quality": "user_supplied",
            "survivorship_bias_free": "unknown",
            "warning": "User-supplied universe quality depends on source completeness and delisted coverage.",
        },
    }


def load_universe_csv(path: str | Path) -> List[UniverseMember]:
    records = []
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(UniverseMember(
                symbol=normalize_symbol(row["symbol"]),
                start_date=parse_date(row.get("start_date") or "1900-01-01"),
                end_date=parse_date(row["end_date"]) if row.get("end_date") else None,
                name=row.get("name", ""),
                sector=row.get("sector", ""),
                source=row.get("source", str(path)),
            ))
    return records


def wikipedia_sp500_members(as_of: date) -> tuple[list[str], dict]:
    """Reconstruct S&P 500 membership from Wikipedia current table + selected changes."""
    import pandas as pd
    import requests

    response = requests.get(
        WIKIPEDIA_SP500_URL,
        headers={"User-Agent": "quant-lab-research/0.1 (+https://wikipedia.org)"},
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    current = tables[0]
    changes = tables[1]
    members = {normalize_symbol(symbol) for symbol in current["Symbol"].dropna().astype(str)}

    parsed_changes = []
    for _, row in changes.iterrows():
        change_date = pd.to_datetime(str(row.iloc[0]), errors="coerce")
        if pd.isna(change_date):
            continue
        change_date = change_date.date()
        added = normalize_symbol(str(row.iloc[1])) if len(row) > 1 and str(row.iloc[1]) != "nan" else ""
        removed = normalize_symbol(str(row.iloc[3])) if len(row) > 3 and str(row.iloc[3]) != "nan" else ""
        parsed_changes.append((change_date, added, removed))

    for change_date, added, removed in parsed_changes:
        if change_date > as_of:
            if added:
                members.discard(added)
            if removed:
                members.add(removed)

    return sorted(members), {
        "source": WIKIPEDIA_SP500_URL,
        "quality": "public_wikipedia_selected_changes",
        "survivorship_bias_free": False,
        "warning": (
            "Wikipedia provides current constituents plus selected changes, not a vendor-grade "
            "complete historical constituent/security-master dataset. Use Norgate/CRSP/vendor "
            "exports for production survivorship-bias-free research."
        ),
        "as_of_reconstruction": "current_members_minus_future_additions_plus_future_removals",
    }


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("empty date")
    return datetime.fromisoformat(text[:10]).date()
