from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .models import Signal


ROOT = Path(__file__).resolve().parents[1]
NOTIFIED_SIGNALS_PATH = ROOT / "data" / "notified_signals.json"


def telegram(method: str, params: dict) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")
    url = f"https://api.telegram.org/bot{token}/{method}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Telegram API connection failed: {exc.reason}") from exc


def send_telegram_message(text: str) -> None:
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set.")
    telegram("sendMessage", {"chat_id": chat_id, "text": text})


def format_signal(signal: Signal) -> str:
    reasons = "\n".join(f"- {reason}" for reason in signal.reasons)
    return (
        f"{signal.action} {signal.symbol} x {signal.suggested_qty}\n"
        f"발생: {signal.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"가격: {signal.price:,.2f}\n"
        f"확신도: {signal.confidence:.0%}\n"
        f"신호 ID: {signal.id}\n"
        f"이유:\n{reasons}\n\n"
        f"승인: /approve {signal.id}"
    )


def notify_new_signals(signals: list[Signal]) -> int:
    if not signals:
        return 0

    notified = _load_notified_signal_ids()
    sent = 0
    for signal in signals:
        if signal.id in notified:
            continue
        send_telegram_message(format_signal(signal))
        notified.add(signal.id)
        sent += 1
    _save_notified_signal_ids(notified)
    return sent


def _load_notified_signal_ids() -> set[str]:
    if not NOTIFIED_SIGNALS_PATH.exists():
        return set()
    try:
        return set(json.loads(NOTIFIED_SIGNALS_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_notified_signal_ids(signal_ids: set[str]) -> None:
    NOTIFIED_SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTIFIED_SIGNALS_PATH.write_text(
        json.dumps(sorted(signal_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
