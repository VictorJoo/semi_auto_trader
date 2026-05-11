from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .models import PriceBar


def load_prices(path: Path) -> list[PriceBar]:
    if not path.exists():
        return []
    return _load_csv(path)


def _load_csv(path: Path) -> list[PriceBar]:
    bars: list[PriceBar] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "symbol", "close"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("CSV must include date,symbol,close columns.")
        for row in reader:
            raw_volume = row.get("volume")
            bars.append(
                PriceBar(
                    date=date.fromisoformat(row["date"]),
                    symbol=row["symbol"].strip().upper(),
                    close=float(row["close"]),
                    volume=int(float(raw_volume)) if raw_volume else 0,
                )
            )
    return sorted(bars, key=lambda bar: (bar.symbol, bar.date))


def group_by_symbol(bars: list[PriceBar]) -> dict[str, list[PriceBar]]:
    grouped: dict[str, list[PriceBar]] = {}
    for bar in bars:
        grouped.setdefault(bar.symbol, []).append(bar)
    return {symbol: sorted(items, key=lambda bar: bar.date) for symbol, items in grouped.items()}
