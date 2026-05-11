from __future__ import annotations

import os
import time
from pathlib import Path

from .core import TradingApp
from .env import load_dotenv
from .notifications import format_signal, send_telegram_message, telegram


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
APP = TradingApp()


def notify_signals() -> None:
    for signal in APP.signals():
        send_telegram_message(format_signal(signal))


def handle_command(text: str) -> str:
    parts = text.strip().split()
    command = parts[0].lower() if parts else ""
    if command == "/status":
        snapshot = APP.snapshot()
        return (
            f"총 평가금액: {snapshot['total_value']:,.0f}\n"
            f"현금: {snapshot['cash']:,.0f}\n"
            f"보유 종목: {len(snapshot['positions'])}"
        )
    if command == "/signals":
        signals = APP.signals()
        return "\n\n".join(format_signal(signal) for signal in signals) or "현재 매수/매도 신호가 없습니다."
    if command == "/approve" and len(parts) == 2:
        trade = APP.execute_signal(parts[1])
        broker = trade.get("external_order", {}).get("provider", "paper")
        return f"주문 완료({broker}): {trade['action']} {trade['symbol']} x {trade['qty']} @ {trade['price']:,.2f}"
    if command in ("/buy", "/sell") and len(parts) == 3:
        action = command.removeprefix("/").upper()
        trade = APP.place_order(parts[1], action, int(parts[2]), "Telegram manual order")
        broker = trade.get("external_order", {}).get("provider", "paper")
        return f"주문 완료({broker}): {trade['action']} {trade['symbol']} x {trade['qty']} @ {trade['price']:,.2f}"
    return "명령을 이해하지 못했습니다. /status, /signals, /approve SIGNAL_ID, /buy SYMBOL QTY, /sell SYMBOL QTY"


def poll() -> None:
    offset = 0
    send_telegram_message("모의투자 봇이 시작되었습니다. /signals 로 현재 신호를 확인하세요.")
    notify_signals()
    while True:
        updates = telegram("getUpdates", {"offset": offset, "timeout": 20})
        for item in updates.get("result", []):
            offset = item["update_id"] + 1
            message = item.get("message", {})
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))
            if CHAT_ID and chat_id != CHAT_ID:
                continue
            try:
                reply = handle_command(text)
            except Exception as exc:
                reply = f"오류: {exc}"
            telegram("sendMessage", {"chat_id": chat_id, "text": reply})
        time.sleep(1)


if __name__ == "__main__":
    poll()
