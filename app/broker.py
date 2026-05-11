from __future__ import annotations

from datetime import datetime

from .models import Portfolio, Position, Trade


class PaperBroker:
    def __init__(self, portfolio: Portfolio | None = None) -> None:
        self.portfolio = portfolio or Portfolio()

    def buy(self, symbol: str, qty: int, price: float, reason: str) -> Trade:
        cost = qty * price
        if qty <= 0:
            raise ValueError("Quantity must be positive.")
        if cost > self.portfolio.cash:
            raise ValueError("Not enough paper cash.")

        position = self.portfolio.positions.get(symbol)
        if position is None:
            self.portfolio.positions[symbol] = Position(symbol=symbol, qty=qty, avg_price=price)
        else:
            new_qty = position.qty + qty
            position.avg_price = ((position.avg_price * position.qty) + cost) / new_qty
            position.qty = new_qty
        self.portfolio.cash -= cost
        trade = Trade(datetime.now(), symbol, "BUY", qty, price, reason)
        self.portfolio.trades.insert(0, trade)
        return trade

    def sell(self, symbol: str, qty: int, price: float, reason: str) -> Trade:
        if qty <= 0:
            raise ValueError("Quantity must be positive.")
        position = self.portfolio.positions.get(symbol)
        if position is None or position.qty < qty:
            raise ValueError("Not enough paper position.")
        position.qty -= qty
        if position.qty == 0:
            del self.portfolio.positions[symbol]
        self.portfolio.cash += qty * price
        trade = Trade(datetime.now(), symbol, "SELL", qty, price, reason)
        self.portfolio.trades.insert(0, trade)
        return trade

