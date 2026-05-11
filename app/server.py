from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import TradingApp
from .notifications import notify_new_signals


APP = TradingApp()


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value)!r} is not JSON serializable")


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003 - http.server signature
        sys.stderr.write(f"[api] {self.address_string()} - {format % args}\n")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/snapshot":
                self.send_json(APP.snapshot())
                return
            if parsed.path == "/api/market":
                params = parse_qs(parsed.query)
                self.send_json(
                    APP.market_snapshot(
                        symbol=(params.get("symbol") or [""])[0],
                        period=(params.get("period") or ["day"])[0],
                    )
                )
                return
            if parsed.path == "/api/refresh":
                APP.refresh()
                notified = notify_new_signals(APP.signals())
                self.send_json({"ok": True, "notified": notified})
                return
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        payload = json.loads(body or "{}")

        try:
            if parsed.path == "/api/approve":
                qty = payload.get("qty")
                trade = APP.execute_signal(
                    payload["signal_id"],
                    int(qty) if qty else None,
                )
                self.send_json({"ok": True, "trade": trade})
                return
            if parsed.path == "/api/order":
                trade = APP.place_order(
                    payload["symbol"],
                    payload["action"],
                    int(payload["qty"]),
                    payload.get("reason", "Dashboard manual order"),
                )
                self.send_json({"ok": True, "trade": trade})
                return
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        self.send_error(404)

    def send_json(self, payload, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Credentials", "true")


def main() -> None:
    port = int(os.getenv("PORT", sys.argv[1] if len(sys.argv) > 1 else "8765"))
    host = os.getenv("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"API: http://{host}:{port}/api")
    try:
        notified = notify_new_signals(APP.signals())
        print(f"Telegram notifications sent: {notified}")
    except Exception as exc:
        print(f"Telegram notification skipped: {exc}")
    server.serve_forever()


if __name__ == "__main__":
    main()
