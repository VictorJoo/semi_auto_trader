from __future__ import annotations

import os
import re
import threading
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
        self._chart_cache: dict[
            tuple[str, str], tuple[float, list[dict[str, Any]]]
        ] = {}
        self._chart_locks: dict[tuple[str, str], threading.Lock] = {}
        self._chart_lock_registry = threading.Lock()
        self._volume_rank_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._name_cache: dict[str, str] = {}

    def refresh(self) -> None:
        self.bars = load_prices(DATA_PATH)
        self.by_symbol = group_by_symbol(self.bars)

    def latest_prices(self) -> dict[str, float]:
        return {symbol: bars[-1].close for symbol, bars in self.by_symbol.items() if bars}

    _SUPPORTED_PERIODS = ("today", "1d", "1w", "3m")

    def market_snapshot(self, symbol: str | None = None, period: str = "today") -> dict[str, Any]:
        period = period if period in self._SUPPORTED_PERIODS else "today"
        if self.is_kis_enabled():
            return self._kis_market_snapshot(symbol or "", period)
        return self._local_market_snapshot(symbol or "", period)

    def _local_market_snapshot(self, symbol: str, period: str) -> dict[str, Any]:
        selected = self.resolve_symbol(symbol)
        if selected not in self.by_symbol:
            selected = next(iter(sorted(self.by_symbol)), "")
        quote = self.live_quote(selected) if selected else None
        return {
            "symbols": [
                {"code": code, "name": ""} for code in sorted(self.by_symbol)
            ],
            "selected_symbol": selected,
            "period": period,
            "quote": quote,
            "chart": self.chart_points(selected, period) if selected else [],
            "top_volume": self.top_volume(limit=5),
            "collected_at": datetime.now(),
        }

    def _kis_market_snapshot(self, symbol: str, period: str) -> dict[str, Any]:
        client = KisApiClient(KisConfig.from_env())
        top_volume_raw = self._cached_kis_volume_ranking(client, limit=30)
        discovery: list[str] = [row["symbol"] for row in top_volume_raw]
        if self._account_cache:
            for position in self._account_cache[1].get("positions") or []:
                try:
                    code = self.to_kis_domestic_symbol(position.get("symbol", ""))
                except ValueError:
                    continue
                discovery.append(code)
                position_name = (position.get("name") or "").strip()
                if position_name and position_name != code:
                    self._name_cache[code] = position_name
        requested_code = self._resolve_query_to_code(symbol) if symbol else ""
        if requested_code:
            discovery.append(requested_code)
        discovery_sorted = sorted(dict.fromkeys(code for code in discovery if code))
        selected = requested_code or (discovery_sorted[0] if discovery_sorted else "")
        quote = self._kis_quote(client, selected) if selected else None
        chart = self._kis_chart_points(client, selected, period) if selected else []

        return {
            "symbols": [
                {"code": code, "name": self._name_cache.get(code, "")}
                for code in discovery_sorted
            ],
            "selected_symbol": selected,
            "period": period,
            "quote": quote,
            "chart": chart,
            "top_volume": [
                {
                    "symbol": row["symbol"],
                    "name": (row.get("name") or "").strip(),
                    "price": row.get("price", 0),
                    "change_pct": row.get("change_pct", 0),
                    "volume": row.get("volume", 0),
                }
                for row in top_volume_raw
            ][:5],
            "collected_at": datetime.now(),
        }

    def _resolve_query_to_code(self, query: str) -> str:
        if not query:
            return ""
        cleaned = query.strip()
        try:
            return self.to_kis_domestic_symbol(cleaned)
        except ValueError:
            pass
        if not self._name_cache:
            return ""
        needle = cleaned.lower()
        for code, name in self._name_cache.items():
            if not name:
                continue
            if name.lower() == needle:
                return code
        for code, name in self._name_cache.items():
            if not name:
                continue
            if needle in name.lower() or name.lower() in needle:
                return code
        return ""

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
        for row in rows:
            symbol = row.get("symbol")
            name = (row.get("name") or "").strip()
            if symbol and name:
                self._name_cache[symbol] = name
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
        name = (output.get("hts_kor_isnm") or "").strip()
        if name:
            self._name_cache[code] = name
        quote = {
            "symbol": code,
            "name": name or self._name_cache.get(code, ""),
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "time": datetime.now(),
        }
        self._quote_cache[code] = (now, quote)
        return quote

    _MARKET_OPEN_MIN = 9 * 60
    _MARKET_CLOSE_MIN = 15 * 60 + 30
    _PRE_MARKET_OPEN_MIN = 8 * 60
    _AFTER_MARKET_CLOSE_MIN = 18 * 60

    @staticmethod
    def _classify_session(min_of_day: int) -> str:
        if min_of_day < 9 * 60:
            return "pre"
        if min_of_day <= 15 * 60 + 30:
            return "regular"
        return "after"

    _CHART_TTL = {
        "today": 60.0,
        "1d": 60.0,
        "1w": 300.0,
        "3m": 1800.0,
    }

    def _kis_chart_points(
        self, client: KisApiClient, code: str, period: str
    ) -> list[dict[str, Any]]:
        cache_key = (code, period)
        now_ts = monotonic()
        cached = self._chart_cache.get(cache_key)
        ttl = self._CHART_TTL.get(period, 60.0)
        if cached and now_ts - cached[0] <= ttl:
            return cached[1]

        lock = self._get_chart_lock(cache_key)
        with lock:
            cached = self._chart_cache.get(cache_key)
            if cached and monotonic() - cached[0] <= ttl:
                return cached[1]
            if period == "today":
                points = self._kis_today_chart(client, code)
            elif period == "1d":
                points = self._kis_1day_chart(client, code)
            elif period == "1w":
                points = self._kis_1week_chart(client, code)
            elif period == "3m":
                points = self._kis_3month_chart(client, code)
            else:
                points = []
            self._chart_cache[cache_key] = (monotonic(), points)
            return points

    def _get_chart_lock(self, key: tuple[str, str]) -> threading.Lock:
        with self._chart_lock_registry:
            lock = self._chart_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._chart_locks[key] = lock
            return lock

    def _cached_kis_daily_candles(
        self, client: KisApiClient, code: str, *, days_back: int = 60
    ) -> list[dict[str, Any]]:
        cache_window = days_back
        now = monotonic()
        cached = self._daily_candle_cache.get(code)
        if cached and now - cached[0] <= 600 and len(cached[1]) >= min(cache_window, 30):
            return cached[1]
        try:
            rows = client.get_domestic_daily_candles(code, days_back=days_back)
        except Exception:
            rows = []
        self._daily_candle_cache[code] = (now, rows)
        return rows

    def _kis_today_chart(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        return self._kis_intraday_chart(
            client,
            code,
            from_min=self._MARKET_OPEN_MIN,
            to_max_min=self._MARKET_CLOSE_MIN,
            bucket_min=5,
        )

    def _kis_1day_chart(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        return self._kis_intraday_chart(
            client,
            code,
            from_min=self._PRE_MARKET_OPEN_MIN,
            to_max_min=self._AFTER_MARKET_CLOSE_MIN,
            bucket_min=5,
        )

    def _kis_intraday_chart(
        self,
        client: KisApiClient,
        code: str,
        *,
        from_min: int,
        to_max_min: int,
        bucket_min: int,
    ) -> list[dict[str, Any]]:
        now = datetime.now()
        today_iso = now.date().isoformat()
        end_min = min(now.hour * 60 + now.minute, to_max_min)
        if end_min < from_min:
            return []

        end_hhmmss = self._minute_to_hhmmss(end_min)
        collected: dict[str, dict[str, Any]] = {}
        max_calls = 2
        for _ in range(max_calls):
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
                if row.get("date") and row["date"] != today_iso:
                    continue
                try:
                    bar_min = int(time_str[:2]) * 60 + int(time_str[2:4])
                except (TypeError, ValueError):
                    continue
                if bar_min < from_min or bar_min > to_max_min:
                    continue
                batch_min.append(bar_min)
                if time_str in collected:
                    continue
                collected[time_str] = row
                new_added = True
            if not new_added or not batch_min:
                break
            earliest = min(batch_min)
            if earliest <= from_min:
                break
            next_end = earliest - 1
            if next_end < from_min:
                break
            end_hhmmss = self._minute_to_hhmmss(next_end)

        if from_min < self._MARKET_OPEN_MIN:
            self._merge_overtime_bars(client, code, collected, from_min, to_max_min)

        return self._aggregate_intraday_to_points(collected, bucket_min)

    def _merge_overtime_bars(
        self,
        client: KisApiClient,
        code: str,
        collected: dict[str, dict[str, Any]],
        from_min: int,
        to_max_min: int,
    ) -> None:
        overtime_rows: list[dict[str, Any]] = []
        for hour_cls_code in ("1", "2"):
            try:
                overtime_rows.extend(
                    client.get_domestic_overtime_conclusions(
                        code,
                        hour_cls_code=hour_cls_code,
                    )
                )
            except Exception:
                continue
        for row in overtime_rows:
            time_str = row.get("time", "")
            if len(time_str) != 6:
                continue
            try:
                bar_min = int(time_str[:2]) * 60 + int(time_str[2:4])
            except (TypeError, ValueError):
                continue
            if bar_min < from_min or bar_min > to_max_min:
                continue
            if bar_min >= self._MARKET_OPEN_MIN and bar_min <= self._MARKET_CLOSE_MIN:
                continue
            if time_str in collected:
                continue
            collected[time_str] = row

    def _aggregate_intraday_to_points(
        self, raw: dict[str, dict[str, Any]], bucket_min: int
    ) -> list[dict[str, Any]]:
        buckets: dict[int, dict[str, Any]] = {}
        for time_str, row in raw.items():
            try:
                hour = int(time_str[:2])
                minute = int(time_str[2:4])
            except (TypeError, ValueError):
                continue
            bucket_floor = (minute // bucket_min) * bucket_min
            key = hour * 60 + bucket_floor
            previous = buckets.get(key)
            volume = row.get("volume", 0) or 0
            if previous is None or time_str > previous["_t"]:
                buckets[key] = {
                    "_t": time_str,
                    "close": row["close"],
                    "volume": (previous["volume"] if previous else 0) + volume,
                }
            else:
                previous["volume"] += volume

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
                    "session": self._classify_session(key),
                }
            )
        if points:
            points[-1]["realtime"] = True
        return points

    def _kis_1week_chart(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        target_days = 5
        today = date.today()
        cutoff = today - timedelta(days=8)

        end_hhmmss = self._minute_to_hhmmss(self._MARKET_CLOSE_MIN)
        seen_keys: set[tuple[str, str]] = set()
        collected: list[dict[str, Any]] = []
        earliest_seen: tuple[str, str] | None = None

        for call_index in range(8):
            try:
                batch = client.get_domestic_minute_candles(
                    code,
                    end_hhmmss=end_hhmmss,
                    include_past_day=True,
                )
            except Exception:
                break
            if not batch:
                break

            new_added = False
            for row in batch:
                row_date = row.get("date") or today.isoformat()
                row_time = row["time"]
                try:
                    bar_day = date.fromisoformat(row_date)
                except ValueError:
                    continue
                if bar_day < cutoff:
                    continue
                try:
                    bar_min = int(row_time[:2]) * 60 + int(row_time[2:4])
                except (TypeError, ValueError):
                    continue
                if (
                    bar_min < self._MARKET_OPEN_MIN
                    or bar_min > self._MARKET_CLOSE_MIN
                ):
                    continue
                key = (row_date, row_time)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                collected.append({**row, "date": row_date})
                new_added = True

            if not new_added:
                break

            batch_sorted = sorted(
                batch,
                key=lambda r: ((r.get("date") or ""), r.get("time") or ""),
            )
            first = batch_sorted[0]
            first_key = (first.get("date") or "", first.get("time") or "")
            if earliest_seen is not None and first_key >= earliest_seen:
                break
            earliest_seen = first_key

            unique_days = sorted({key[0] for key in seen_keys})
            if len(unique_days) >= target_days + 1:
                break

            first_date = first.get("date") or today.isoformat()
            first_time = first.get("time") or end_hhmmss
            try:
                first_day = date.fromisoformat(first_date)
            except ValueError:
                break
            first_min = int(first_time[:2]) * 60 + int(first_time[2:4])
            if first_min - 1 >= self._MARKET_OPEN_MIN:
                next_end = first_min - 1
                end_hhmmss = self._minute_to_hhmmss(next_end)
            else:
                prev_day = first_day - timedelta(days=1)
                while prev_day.weekday() >= 5:
                    prev_day -= timedelta(days=1)
                if prev_day < cutoff:
                    break
                end_hhmmss = self._minute_to_hhmmss(self._MARKET_CLOSE_MIN)

        return self._aggregate_week_to_points(collected, bucket_min=10, days_window=target_days)

    def _aggregate_week_to_points(
        self,
        rows: list[dict[str, Any]],
        *,
        bucket_min: int,
        days_window: int,
    ) -> list[dict[str, Any]]:
        unique_days = sorted({row["date"] for row in rows if row.get("date")})
        if not unique_days:
            return []
        keep_days = set(unique_days[-days_window:])

        buckets: dict[tuple[str, int], dict[str, Any]] = {}
        for row in rows:
            row_date = row.get("date")
            if not row_date or row_date not in keep_days:
                continue
            time_str = row["time"]
            try:
                hour = int(time_str[:2])
                minute = int(time_str[2:4])
            except (TypeError, ValueError):
                continue
            bucket_floor = (minute // bucket_min) * bucket_min
            key = (row_date, hour * 60 + bucket_floor)
            previous = buckets.get(key)
            volume = row.get("volume", 0) or 0
            if previous is None or time_str > previous["_t"]:
                buckets[key] = {
                    "_t": time_str,
                    "close": row["close"],
                    "volume": (previous["volume"] if previous else 0) + volume,
                }
            else:
                previous["volume"] += volume

        points: list[dict[str, Any]] = []
        for key in sorted(buckets):
            row_date, minute_key = key
            hour, minute = divmod(minute_key, 60)
            month_day = row_date[5:].replace("-", "-")
            label = f"{month_day} {hour:02d}:{minute:02d}"
            points.append(
                {
                    "label": label,
                    "tooltip_label": f"{row_date} {hour:02d}:{minute:02d}",
                    "close": buckets[key]["close"],
                    "volume": buckets[key]["volume"],
                    "realtime": False,
                    "session": self._classify_session(minute_key),
                }
            )
        if points:
            points[-1]["realtime"] = True
        return points

    def _kis_3month_chart(
        self, client: KisApiClient, code: str
    ) -> list[dict[str, Any]]:
        candles = self._cached_kis_daily_candles(client, code, days_back=100)
        if not candles:
            return []
        today = date.today()
        cutoff = today - timedelta(days=92)
        filtered = [
            row
            for row in candles
            if cutoff <= date.fromisoformat(row["date"]) <= today
        ]
        points = [
            {
                "label": date.fromisoformat(row["date"]).strftime("%m-%d"),
                "tooltip_label": row["date"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for row in filtered
        ]
        if points:
            points[-1]["realtime"] = True
        return points

    @staticmethod
    def _minute_to_hhmmss(total_min: int) -> str:
        total_min = max(0, min(total_min, 24 * 60 - 1))
        return f"{total_min // 60:02d}{total_min % 60:02d}00"

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
        if period == "1w":
            return self._daily_points(bars, days=7)
        if period == "3m":
            return self._daily_points(bars, days=90)
        if period == "1d":
            return self._daily_points(bars, days=1)
        return self._daily_points(bars, days=1)

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

    def account_env(self) -> str:
        return os.getenv("KIS_ACCOUNT_ENV", os.getenv("BROKER_ENV", "paper")).strip().lower()

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
            generate_signal(self.display_symbol_for_signal(symbol), bars, buying_power)
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
        if self.is_kis_enabled():
            allowed_symbols = {self.display_symbol_for_signal(symbol) for symbol in allowed_symbols}
        return merge_active_signals(signals, allowed_symbols=allowed_symbols)

    def display_symbol_for_signal(self, symbol: str) -> str:
        if not self.is_kis_enabled():
            return symbol
        try:
            return self.to_kis_domestic_symbol(symbol)
        except ValueError:
            return symbol

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
        self._chart_cache.clear()
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
        client = KisApiClient(KisConfig.from_env(env=self.account_env()))
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
            avg_price = self._to_float(item.get("pchs_avg_pric"))
            current_price = self._to_float(item.get("prpr"))
            value = self._to_float(item.get("evlu_amt")) or qty * current_price
            market_value += value
            position_name = (item.get("prdt_name") or "").strip()
            if symbol and position_name:
                self._name_cache[symbol] = position_name
            positions.append(
                {
                    "symbol": symbol,
                    "name": position_name or symbol,
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
            "source": f"korea_investment_{self.account_env()}",
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
