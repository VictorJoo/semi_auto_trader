from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import Portfolio, Position, Trade


def _default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value)!r} is not JSON serializable")


def save_portfolio(path: Path, portfolio: Portfolio) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cash": portfolio.cash,
        "positions": {symbol: asdict(position) for symbol, position in portfolio.positions.items()},
        "trades": [asdict(trade) for trade in portfolio.trades],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_default), encoding="utf-8")


def load_portfolio(path: Path) -> Portfolio:
    if not path.exists():
        return Portfolio()
    payload = json.loads(path.read_text(encoding="utf-8"))
    positions = {
        symbol: Position(symbol=value["symbol"], qty=int(value["qty"]), avg_price=float(value["avg_price"]))
        for symbol, value in payload.get("positions", {}).items()
    }
    trades = [
        Trade(
            created_at=datetime.fromisoformat(item["created_at"]),
            symbol=item["symbol"],
            action=item["action"],
            qty=int(item["qty"]),
            price=float(item["price"]),
            reason=item["reason"],
        )
        for item in payload.get("trades", [])
    ]
    return Portfolio(cash=float(payload.get("cash", 10_000_000.0)), positions=positions, trades=trades)

