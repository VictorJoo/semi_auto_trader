from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class PriceBar:
    date: date
    symbol: str
    close: float
    volume: int = 0


@dataclass(frozen=True)
class Signal:
    id: str
    created_at: datetime
    symbol: str
    action: str
    price: float
    confidence: float
    reasons: list[str]
    suggested_qty: int


@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float


@dataclass
class Trade:
    created_at: datetime
    symbol: str
    action: str
    qty: int
    price: float
    reason: str


@dataclass
class Portfolio:
    cash: float = 10_000_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

