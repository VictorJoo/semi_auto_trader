from __future__ import annotations

import os
from pathlib import Path

from .env import load_dotenv
from .notifications import send_telegram_message, telegram


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")
    configured_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    print("Telegram config")
    print(f"- token: {'set' if os.getenv('TELEGRAM_BOT_TOKEN') else 'missing'}")
    print(f"- chat_id: {'set' if configured_chat_id else 'missing'}")

    me = telegram("getMe", {})
    print(f"- getMe_ok: {bool(me.get('ok'))}")
    print(f"- username_loaded: {bool(me.get('result', {}).get('username'))}")

    updates = telegram("getUpdates", {})
    chats = []
    for item in updates.get("result", []):
        message = item.get("message") or item.get("channel_post") or {}
        chat = message.get("chat") or {}
        if "id" in chat:
            chats.append((chat.get("id"), chat.get("type"), chat.get("title") or chat.get("username") or chat.get("first_name")))
    if chats:
        print("- recent_chats:")
        for chat_id, chat_type, name in chats[-5:]:
            print(f"  chat_id={chat_id} type={chat_type} name={name}")
        recent_ids = {str(chat_id) for chat_id, _, _ in chats}
        if configured_chat_id and configured_chat_id not in recent_ids:
            positive_id = configured_chat_id.removeprefix("-")
            if positive_id in recent_ids:
                print(f"- suggested_fix: TELEGRAM_CHAT_ID={positive_id}")
            else:
                print("- suggested_fix: .env의 TELEGRAM_CHAT_ID를 recent_chats 중 하나로 바꾸세요.")
    else:
        print("- recent_chats: none")
        print("- suggested_fix: 봇에게 텔레그램에서 /start 또는 아무 메시지나 보낸 뒤 다시 실행하세요.")

    try:
        send_telegram_message("텔레그램 진단 메시지입니다.")
        print("- test_message_sent: True")
    except Exception as exc:
        print(f"- test_message_sent: False")
        print(f"- error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
