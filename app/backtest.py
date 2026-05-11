from __future__ import annotations

from dataclasses import dataclass

from .models import PriceBar, Trade
from .strategy import generate_signal


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    start_cash: float
    final_value: float
    return_pct: float
    trades: list[Trade]


def run_backtest(symbol: str, bars: list[PriceBar], start_cash: float = 10_000_000.0) -> BacktestResult:
    cash = start_cash
    qty = 0
    trades: list[Trade] = []

    for index in range(35, len(bars)):
        window = bars[: index + 1]
        signal = generate_signal(symbol, window, cash)
        if signal is None:
            continue
        price = window[-1].close
        if signal.action == "BUY" and cash >= price:
            order_qty = min(signal.suggested_qty, int(cash // price))
            if order_qty <= 0:
                continue
            cash -= order_qty * price
            qty += order_qty
            trades.append(Trade(signal.created_at, symbol, "BUY", order_qty, price, "; ".join(signal.reasons)))
        elif signal.action == "SELL" and qty > 0:
            order_qty = min(signal.suggested_qty, qty)
            cash += order_qty * price
            qty -= order_qty
            trades.append(Trade(signal.created_at, symbol, "SELL", order_qty, price, "; ".join(signal.reasons)))

    final_value = cash + qty * bars[-1].close
    return BacktestResult(
        symbol=symbol,
        start_cash=start_cash,
        final_value=final_value,
        return_pct=(final_value / start_cash - 1) * 100,
        trades=trades,
    )

