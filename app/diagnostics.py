from __future__ import annotations

import os
from pathlib import Path

from .env import load_dotenv
from .kis_api import KisApiClient, KisConfig


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")

    keys = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "BROKER_PROVIDER",
        "BROKER_ENV",
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
        "KIS_ACCOUNT_NO",
        "KIS_ACCOUNT_PRODUCT_CODE",
    ]
    print("Environment")
    for key in keys:
        value = os.getenv(key, "")
        suffix = f" len={len(value)}" if value else ""
        print(f"- {key}: {'set' if value else 'missing'}{suffix}")

    print("\nKIS config")
    config = KisConfig.from_env()
    print(f"- env: {config.env}")
    print(f"- account_no_len: {len(config.account_no)}")
    print(f"- product_code: {config.account_product_code}")
    print(f"- base_url: {config.base_url}")

    print("\nKIS token")
    try:
        token = KisApiClient(config).access_token()
        print(f"- token_loaded: {bool(token)}")
    except Exception as exc:
        print(f"- token_loaded: False")
        print(f"- error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
