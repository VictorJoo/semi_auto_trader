from __future__ import annotations

import os
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from .backtest import run_backtest
from .broker import PaperBroker
from .data import group_by_symbol, load_prices
from .env import load_dotenv
from .kis_api import KisApiClient, KisConfig
from .models import Signal
from .signal_store import merge_active_signals
from .store import load_portfolio, save_portfolio
from .strategy import generate_signal


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "prices.csv"
PORTFOLIO_PATH = ROOT / "data" / "portfolio.json"
load_dotenv(ROOT / ".env")


class TradingApp:
    def __init__(self) -> None:
        self.bars = load_prices(DATA_PATH)
        self.by_symbol = group_by_symbol(self.bars)
        self.broker = PaperBroker(load_portfolio(PORTFOLIO_PATH))
        self._account_cache: tuple[float, dict[str, Any]] | None = None
        self._price_cache: dict[str, tuple[float, int]] = {}
        self._quote_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._daily_candle_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._minute_candle_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._volume_rank_cache: tuple[float, list[dict[str, Any]]] | None = None

    def refresh(self) -> None:
        self.bars = load_prices(DATA_PATH)
        self.by_symbol = group_by_symbol(self.bars)

    def latest_prices(self) -> dict[str, float]:
        return {symbol: bars[-1].close for symbol, bars in self.by_symbol.items() if bars}

    def market_snapshot(self, symbol: str | None = None, period: str = "day") -> dict[str, Any]:
        period = period if period in {"day", "week", "month"} else "day"
        if self.is_kis_enabled():
            return self._kis_market_snapshot(symbol or "", period)
        return self._local_market_snapshot(symbol or "", period)

    def _local_market_snapshot(self, symbol: str, period: str) -> dict[str, Any]:
        selected = self.resolve_symbol(symbol)
        if selected not in self.by_symbol:
            selected = next(iter(sorted(self.by_symbol)), "")
        quote = self.live_quote(selected) if selected else None
        return {
            "symbols": sorted(self.by_symbol),
            "selected_symbol": selected,
            "period": period,
            "quote": quote,
            "chart": self.chart_points(selected, period) if selected else [],
            "top_volume": self.top_volume(limit=5),
            "collected_at": datetime.now(),
        }

    def _kis_market_snapshot(self, symbol: str, period: str) -> dict[str, Any]:
        client = KisApiClient(KisConfig.from_env())
        top_volume_raw = self._cached_kis_volume_ranking(client, limit=5)
        discovery: list[str] = [row["symbol"] for row in top_volume_raw]
        for position in self._safe_account_positions():
            try:
                discovery.append(self.to_kis_domestic_symbol(position.get("symbol", "")))
            except ValueError:
                continue
        requested_code = ""
        if symbol:
            try:
                requested_code = self.to_kis_domestic_symbol(symbol)
                discovery.append(requested_code)
            except ValueError:
                requested_code = ""
        discovery_sorted = sorted(dict.fromkeys(code for code in discovery if code))
        selected = requested_code or (discovery_sorted[0] if discovery_sorted else "")
        quote = self._kis_quote(client, selected) if selected else None
        chart = self._kis_chart_points(client, selected, period) if selected else []

        def render(code: str) -> str:
            return f"{code}.KS" if code else ""

        return {
            "symbols": [render(code) for code in discovery_sorted],
            "selected_symbol": render(selected),
            "period": period,
            "quote": quote,
            "chart": chart,
            "top_volume": [
                {**row, "symbol": render(row["symbol"])} for row in top_volume_raw
            ],
            "collected_at": datetime.now(),
        }

    def _safe_account_positions(self) -> list[dict[str, Any]]:
        try:
            return self.account_snapshot().get("positions") or []
        except Exception:
            return []

    def _cached_kis_volume_ranking(
        self, client: KisApiClient, *, limit: int
    ) -> list[dict[str, Any]]:
        now = monotonic()
        if self._volume_rank_cache and now - self._volume_rank_cache[0] <= 60:
            return self._volume_rank_cache[1][:limit]
        try:
            rows = client.get_domestic_volume_ranking(limit=max(limit, 10))
        except Exception:
            rows = []
        self._volume_rank_cache = (now, rows)
        return rows[:limit]

    def _kis_quote(self, client: KisApiClient, code: str) -> dict[str, Any] | None:
        now = monotonic()
        cached = self._quote_cache.get(code)
        if cached and now - cached[0] <= 2:
            return cached[1]
        try:
            output = client.get_domestic_quote(code)
        except Exception:
            return None
        if not output:
            return None
        try:
            price = float(output.get("stck_prpr") or 0)
            change = float(output.get("prdy_vrss") or 0)
            change_pct = float(output.get("prdy_ctrt") or 0)
            volume = int(float(output.get("acml_vol") or 0))
        except (TypeError, ValueError):
            return None
        sign = str(output.get("prdy_vrss_sign") or "").strip()
        if sign in {"4", "5"}:
            change = -abs(change)
            change_pct = -abs(change_pct)
        quote = {
            "symbol": f"{code}.KS",
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "time": datetime.now(),
        }
        self._quote_cache[code] = (now, quote)
        return quote

    def _kis_chart_points(
        self, client: KisApiClient, code: str, period: str
    ) -> list[dict[str, Any]]:
        if period == "day":
            return self._kis_minute_chart(client, code)
        days = 7 if period == "week" else 28
        candles = self._cached_kis_daily_candles(client, code)
        if not candles:
            return []
        today = date.today()
        cutoff = today - timedelta(days=days - 1)
        filtered = [
            row for row in candles if cutoff <= date.fromisoformat(row["date"]) <= today
        ]
        if period == "week":
            return [
                {
                    "label": date.fromisoformat(row["date"]).strftime("%m-%d"),
                    "tooltip_label": row["date"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                for row in filtered
            ]
        grouped: dict[str, dict[str, Any]] = {}
        for row in filtered:
            day = date.fromisoformat(row["date"])
            week_start = day - timedelta(days=day.weekday())
            key = week_start.isoformat()
            previous_volume = grouped.get(key, {}).get("volume", 0)
            grouped[key] = {
                "label": week_start.strftime("%m-%d"),
                "tooltip_label": f"{key} 주",
                "close": row["close"],
                "volume": previous_volume + row["volume"],
            }
        return [grouped[key] for key in sorted(grouped)]

    def _cached_kis_daily_candles(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        now = monotonic()
        cached = self._daily_candle_cache.get(code)
        if cached and now - cached[0] <= 600:
            return cached[1]
        try:
            rows = client.get_domestic_daily_candles(code, days_back=60)
        except Exception:
            rows = []
        self._daily_candle_cache[code] = (now, rows)
        return rows

    _MARKET_OPEN_MIN = 9 * 60
    _MARKET_CLOSE_MIN = 15 * 60 + 30

    def _kis_minute_chart(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        now = monotonic()
        cached = self._minute_candle_cache.get(code)
        if cached and now - cached[0] <= 60:
            return cached[1]

        raw = self._collect_kis_minute_bars(client, code)
        buckets: dict[int, dict[str, Any]] = {}
        for time_str, row in raw.items():
            try:
                hour = int(time_str[:2])
                minute = int(time_str[2:4])
            except (TypeError, ValueError):
                continue
            bucket_minute = (minute // 5) * 5
            key = hour * 60 + bucket_minute
            previous = buckets.get(key)
            if previous is None or time_str > previous["_t"]:
                buckets[key] = {
                    "_t": time_str,
                    "close": row["close"],
                    "volume": (previous["volume"] if previous else 0) + row["volume"],
                }
            else:
                previous["volume"] += row["volume"]

        points: list[dict[str, Any]] = []
        for key in sorted(buckets):
            hour, minute = divmod(key, 60)
            label = f"{hour:02d}:{minute:02d}"
            points.append(
                {
                    "label": label,
                    "tooltip_label": label,
                    "close": buckets[key]["close"],
                    "volume": buckets[key]["volume"],
                    "realtime": False,
                }
            )
        if points:
            points[-1]["realtime"] = True
        self._minute_candle_cache[code] = (now, points)
        return points

    def _collect_kis_minute_bars(
        self, client: KisApiClient, code: str
    ) -> dict[str, dict[str, Any]]:
        now = datetime.now()
        end_min = min(now.hour * 60 + now.minute, self._MARKET_CLOSE_MIN)
        if end_min < self._MARKET_OPEN_MIN:
            return {}
        end_hhmmss = f"{end_min // 60:02d}{end_min % 60:02d}00"

        collected: dict[str, dict[str, Any]] = {}
        for _ in range(15):
            try:
                batch = client.get_domestic_minute_candles(
                    code,
                    end_hhmmss=end_hhmmss,
                    include_past_day=False,
                )
            except Exception:
                break
            if not batch:
                break
            new_added = False
            batch_min: list[int] = []
            for row in batch:
                time_str = row["time"]
                try:
                    bar_min = int(time_str[:2]) * 60 + int(time_str[2:4])
                except (TypeError, ValueError):
                    continue
                if (
                    bar_min < self._MARKET_OPEN_MIN
                    or bar_min > self._MARKET_CLOSE_MIN
                ):
                    continue
                batch_min.append(bar_min)
                if time_str in collected:
                    continue
                collected[time_str] = row
                new_added = True
            if not new_added or not batch_min:
                break
            earliest = min(batch_min)
            if earliest <= self._MARKET_OPEN_MIN:
                break
            next_end = earliest - 1
            if next_end < self._MARKET_OPEN_MIN:
                break
            end_hhmmss = f"{next_end // 60:02d}{next_end % 60:02d}00"
        return collected

    def live_quote(self, symbol: str) -> dict[str, Any] | None:
        bars = self.by_symbol.get(symbol, [])
        if not bars:
            return None
        latest = bars[-1]
        previous = bars[-2].close if len(bars) >= 2 else latest.close
        price = latest.close
        change = price - previous
        return {
            "symbol": symbol,
            "price": price,
            "change": change,
            "change_pct": (change / previous) * 100 if previous else 0.0,
            "volume": latest.volume,
            "time": datetime.now(),
        }

    def chart_points(self, symbol: str, period: str) -> list[dict[str, Any]]:
        bars = self.by_symbol.get(symbol, [])
        if period == "week":
            return self._daily_points(bars, days=7)
        if period == "month":
            return self._weekly_points(bars, days=28)
        return self._daily_points(bars, days=14)

    def top_volume(self, limit: int) -> list[dict[str, Any]]:
        items = []
        for symbol, bars in self.by_symbol.items():
            if not bars:
                continue
            latest = bars[-1]
            previous = bars[-2].close if len(bars) >= 2 else latest.close
            items.append(
                {
                    "symbol": symbol,
                    "price": latest.close,
                    "change_pct": ((latest.close / previous) - 1) * 100 if previous else 0.0,
                    "volume": latest.volume,
                }
            )
        return sorted(items, key=lambda item: item["volume"], reverse=True)[:limit]

    def _daily_points(self, bars, days: int) -> list[dict[str, Any]]:
        if not bars:
            return []
        today = datetime.now().date()
        cutoff = today - timedelta(days=days - 1)
        return [
            {
                "label": bar.date.strftime("%m-%d"),
                "tooltip_label": bar.date.isoformat(),
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
            if cutoff <= bar.date <= today
        ]

    def _weekly_points(self, bars, days: int) -> list[dict[str, Any]]:
        if not bars:
            return []
        today = datetime.now().date()
        cutoff = today - timedelta(days=days - 1)
        grouped: dict[str, dict[str, Any]] = {}
        for bar in bars:
            if not cutoff <= bar.date <= today:
                continue
            week_start = bar.date - timedelta(days=bar.date.weekday())
            key = week_start.isoformat()
            grouped[key] = {
                "label": week_start.strftime("%m-%d"),
                "tooltip_label": f"{week_start.isoformat()} 주",
                "close": bar.close,
                "volume": grouped.get(key, {}).get("volume", 0) + bar.volume,
            }
        return [grouped[key] for key in sorted(grouped)]

    def broker_provider(self) -> str:
        return os.getenv("BROKER_PROVIDER", "paper").strip().lower()

    def is_kis_enabled(self) -> bool:
        return self.broker_provider() == "korea_investment"

    def resolve_symbol(self, symbol: str) -> str:
        normalized = symbol.upper().strip()
        if normalized in self.by_symbol:
            return normalized
        if re.fullmatch(r"\d{6}", normalized) and f"{normalized}.KS" in self.by_symbol:
            return f"{normalized}.KS"
        return normalized

    def is_supported_signal_symbol(self, symbol: str) -> bool:
        if not self.is_kis_enabled():
            return True
        try:
            self.to_kis_domestic_symbol(symbol)
            return True
        except ValueError:
            return False

    def signals(self) -> list[Signal]:
        account = self.account_snapshot()
        buying_power = account["cash"]
        held_qty = {position["symbol"]: position["qty"] for position in account["positions"] if position["qty"] > 0}
        generated = [
            generate_signal(symbol, bars, buying_power)
            for symbol, bars in sorted(self.by_symbol.items())
            if self.is_supported_signal_symbol(symbol)
        ]
        signals: list[Signal] = []
        for signal in generated:
            if signal is None:
                continue
            if signal.action == "SELL":
                qty = held_qty.get(signal.symbol, 0)
                if qty <= 0:
                    continue
                signal = Signal(
                    id=signal.id,
                    created_at=signal.created_at,
                    symbol=signal.symbol,
                    action=signal.action,
                    price=signal.price,
                    confidence=signal.confidence,
                    reasons=signal.reasons,
                    suggested_qty=min(signal.suggested_qty, qty),
                )
            signals.append(signal)
        allowed_symbols = {symbol for symbol in self.by_symbol if self.is_supported_signal_symbol(symbol)}
        return merge_active_signals(signals, allowed_symbols=allowed_symbols)

    def execute_signal(self, signal_id: str, qty: int | None = None) -> dict[str, Any]:
        signal = next((item for item in self.signals() if item.id == signal_id), None)
        if signal is None:
            raise ValueError("Signal not found.")
        order_qty = signal.suggested_qty if qty is None else qty
        if order_qty <= 0:
            raise ValueError("Quantity must be positive.")
        if signal.action == "SELL":
            held_qty = {
                position["symbol"]: position["qty"]
                for position in self.account_snapshot()["positions"]
                if position["qty"] > 0
            }.get(signal.symbol, 0)
            if order_qty > held_qty:
                raise ValueError(f"보유 수량보다 많이 매도할 수 없습니다. 보유 수량: {held_qty}")
        return self.place_order(signal.symbol, signal.action, order_qty, f"Approved signal: {signal_id}")

    def place_order(self, symbol: str, action: str, qty: int, reason: str) -> dict[str, Any]:
        symbol = self.resolve_symbol(symbol)
        action = action.upper()
        prices = self.latest_prices()
        if symbol not in prices:
            raise ValueError(f"Unknown symbol: {symbol}")
        price = prices[symbol]
        external_order = self.place_external_order(symbol, action, qty)
        if external_order is not None:
            qty = int(external_order.get("qty", qty))
            price = float(external_order.get("price", price))
            return {
                "created_at": datetime.now(),
                "symbol": symbol,
                "action": action,
                "qty": qty,
                "price": price,
                "reason": reason,
                "external_order": external_order,
            }
        if action == "BUY":
            trade = self.broker.buy(symbol, qty, price, reason)
        elif action == "SELL":
            trade = self.broker.sell(symbol, qty, price, reason)
        else:
            raise ValueError("Action must be BUY or SELL.")
        save_portfolio(PORTFOLIO_PATH, self.broker.portfolio)
        payload = asdict(trade)
        if external_order is not None:
            payload["external_order"] = external_order
        return payload

    def place_external_order(self, symbol: str, action: str, qty: int) -> dict[str, Any] | None:
        provider = self.broker_provider()
        if provider in {"", "paper", "local"}:
            return None
        if provider != "korea_investment":
            raise ValueError(f"Unsupported BROKER_PROVIDER: {provider}")

        domestic_symbol = self.to_kis_domestic_symbol(symbol)
        client = KisApiClient(KisConfig.from_env())
        market_price = self.kis_domestic_price(domestic_symbol, client)
        adjusted = False
        order_qty = qty
        if action.upper() == "BUY":
            max_qty = int(self.account_snapshot()["cash"] // market_price)
            if max_qty <= 0:
                raise ValueError(
                    f"KIS 현재가 기준 매수 가능 수량이 없습니다. "
                    f"현재가 {market_price:,}원"
                )
            if order_qty > max_qty:
                order_qty = max_qty
                adjusted = True
        response = client.order_domestic_stock(domestic_symbol, action, order_qty)
        self.clear_kis_caches()
        return {
            "provider": "korea_investment",
            "env": os.getenv("BROKER_ENV", "paper"),
            "symbol": domestic_symbol,
            "qty": order_qty,
            "price": market_price,
            "adjusted": adjusted,
            "response": response,
        }

    def to_kis_domestic_symbol(self, symbol: str) -> str:
        normalized = symbol.upper().strip()
        if normalized.endswith(".KS"):
            normalized = normalized.removesuffix(".KS")
        if not re.fullmatch(r"\d{6}", normalized):
            raise ValueError(
                "한국투자증권 국내주식 주문은 6자리 국내 종목코드만 지원합니다. "
                "예: 005930 또는 005930.KS"
            )
        return normalized

    def account_snapshot(self) -> dict[str, Any]:
        if self.is_kis_enabled():
            return self.kis_account_snapshot()
        return self.local_account_snapshot()

    def clear_kis_caches(self) -> None:
        self._account_cache = None
        self._price_cache.clear()
        self._quote_cache.clear()
        self._daily_candle_cache.clear()
        self._minute_candle_cache.clear()
        self._volume_rank_cache = None

    def kis_domestic_price(self, symbol: str, client: KisApiClient | None = None) -> int:
        cached = self._price_cache.get(symbol)
        now = monotonic()
        if cached and now - cached[0] <= 3:
            return cached[1]
        client = client or KisApiClient(KisConfig.from_env())
        price = client.get_domestic_price(symbol)
        self._price_cache[symbol] = (now, price)
        return price

    def local_account_snapshot(self) -> dict[str, Any]:
        prices = self.latest_prices()
        positions = []
        market_value = 0.0
        for position in self.broker.portfolio.positions.values():
            current_price = prices.get(position.symbol, position.avg_price)
            value = position.qty * current_price
            market_value += value
            positions.append(
                {
                    "symbol": position.symbol,
                    "name": position.symbol,
                    "qty": position.qty,
                    "avg_price": position.avg_price,
                    "current_price": current_price,
                    "value": value,
                    "pnl_pct": ((current_price / position.avg_price) - 1) * 100,
                }
            )
        return {
            "source": "local_paper",
            "cash": self.broker.portfolio.cash,
            "market_value": market_value,
            "total_value": self.broker.portfolio.cash + market_value,
            "positions": positions,
            "error": None,
        }

    def kis_account_snapshot(self) -> dict[str, Any]:
        now = monotonic()
        if self._account_cache and now - self._account_cache[0] <= 5:
            return self._account_cache[1]
        client = KisApiClient(KisConfig.from_env())
        balance = client.get_domestic_balance()
        raw_positions = balance.get("output1") or []
        summary_items = balance.get("output2") or []
        summary = summary_items[0] if isinstance(summary_items, list) and summary_items else {}

        positions = []
        market_value = 0.0
        for item in raw_positions:
            qty = self._to_int(item.get("hldg_qty"))
            if qty <= 0:
                continue
            symbol = str(item.get("pdno") or "").strip()
            display_symbol = f"{symbol}.KS" if re.fullmatch(r"\d{6}", symbol) else symbol
            avg_price = self._to_float(item.get("pchs_avg_pric"))
            current_price = self._to_float(item.get("prpr"))
            value = self._to_float(item.get("evlu_amt")) or qty * current_price
            market_value += value
            positions.append(
                {
                    "symbol": display_symbol,
                    "name": item.get("prdt_name") or display_symbol,
                    "qty": qty,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "value": value,
                    "pnl_pct": self._to_float(item.get("evlu_pfls_rt")),
                }
            )

        cash = (
            self._to_float(summary.get("dnca_tot_amt"))
            or self._to_float(summary.get("ord_psbl_cash"))
            or self._to_float(summary.get("nass_amt"))
        )
        total_value = self._to_float(summary.get("tot_evlu_amt")) or cash + market_value
        if not market_value:
            market_value = self._to_float(summary.get("scts_evlu_amt"))

        snapshot = {
            "source": "korea_investment",
            "cash": cash,
            "market_value": market_value,
            "total_value": total_value,
            "positions": positions,
            "error": None,
        }
        self._account_cache = (now, snapshot)
        return snapshot

    def _to_int(self, value: Any) -> int:
        try:
            return int(float(str(value).replace(",", "").strip() or "0"))
        except Exception:
            return 0

    def _to_float(self, value: Any) -> float:
        try:
            return float(str(value).replace(",", "").strip() or "0")
        except Exception:
            return 0.0

    def snapshot(self) -> dict[str, Any]:
        prices = self.latest_prices()
        try:
            account = self.account_snapshot()
        except Exception as exc:
            account = {
                "source": self.broker_provider(),
                "cash": 0.0,
                "market_value": 0.0,
                "total_value": 0.0,
                "positions": [],
                "error": str(exc),
            }

        backtests = [
            run_backtest(symbol, bars)
            for symbol, bars in sorted(self.by_symbol.items())
            if len(bars) >= 35
        ]

        return {
            "broker_source": account["source"],
            "broker_error": account["error"],
            "cash": account["cash"],
            "market_value": account["market_value"],
            "total_value": account["total_value"],
            "prices": prices,
            "positions": account["positions"],
            "signals": self.serialized_signals(),
            "trades": [] if self.is_kis_enabled() else [asdict(trade) for trade in self.broker.portfolio.trades[:20]],
            "backtests": [
                {
                    "symbol": result.symbol,
                    "start_cash": result.start_cash,
                    "final_value": result.final_value,
                    "return_pct": result.return_pct,
                    "trade_count": len(result.trades),
                }
                for result in backtests
            ],
        }

    def serialized_signals(self) -> list[dict[str, Any]]:
        try:
            return [asdict(signal) for signal in self.signals()]
        except Exception:
            return []
