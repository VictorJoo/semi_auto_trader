from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import Signal


ROOT = Path(__file__).resolve().parents[1]
SIGNALS_PATH = ROOT / "data" / "signals.json"


def load_active_signals(path: Path = SIGNALS_PATH, allowed_symbols: set[str] | None = None) -> dict[str, Signal]:
    if not path.exists():
        return {}
    today = datetime.now().date()
    active: dict[str, Signal] = {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    for item in payload:
        try:
            signal = Signal(
                id=item["id"],
                created_at=datetime.fromisoformat(item["created_at"]),
                symbol=item["symbol"],
                action=item["action"],
                price=float(item["price"]),
                confidence=float(item["confidence"]),
                reasons=list(item["reasons"]),
                suggested_qty=int(item["suggested_qty"]),
            )
        except Exception:
            continue
        if allowed_symbols is not None and signal.symbol not in allowed_symbols:
            continue
        if signal.created_at.date() == today:
            active[signal.id] = signal
    return active


def merge_active_signals(
    generated: list[Signal],
    path: Path = SIGNALS_PATH,
    allowed_symbols: set[str] | None = None,
) -> list[Signal]:
    active = load_active_signals(path, allowed_symbols=allowed_symbols)
    for signal in generated:
        active.setdefault(signal.id, signal)
    signals = sorted(active.values(), key=lambda item: item.created_at, reverse=True)
    save_signals(signals, path)
    return signals


def save_signals(signals: list[Signal], path: Path = SIGNALS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(signal) for signal in signals]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    raise TypeError(f"{type(value)!r} is not JSON serializable")
