from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


LIVE_BASE_URL = "https://openapi.koreainvestment.com:9443"
PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
_KIS_LOCK = threading.Lock()
_KIS_LAST_REQUEST_AT = 0.0
_KIS_MIN_INTERVAL_SECONDS = 0.35


@dataclass(frozen=True)
class KisConfig:
    app_key: str
    app_secret: str
    account_no: str
    account_product_code: str
    env: str = "paper"

    @property
    def base_url(self) -> str:
        return PAPER_BASE_URL if self.env == "paper" else LIVE_BASE_URL

    @classmethod
    def from_env(cls) -> "KisConfig":
        required = {
            "KIS_APP_KEY": os.getenv("KIS_APP_KEY", ""),
            "KIS_APP_SECRET": os.getenv("KIS_APP_SECRET", ""),
            "KIS_ACCOUNT_NO": os.getenv("KIS_ACCOUNT_NO", ""),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing KIS environment variables: {', '.join(missing)}")
        return cls(
            app_key=required["KIS_APP_KEY"],
            app_secret=required["KIS_APP_SECRET"],
            account_no=required["KIS_ACCOUNT_NO"],
            account_product_code=os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01"),
            env=os.getenv("BROKER_ENV", "paper"),
        )


class KisApiClient:
    def __init__(self, config: KisConfig, token_cache_dir: Path | None = None) -> None:
        self.config = config
        self._access_token: str | None = None
        self.token_cache_dir = token_cache_dir or Path(__file__).resolve().parents[1] / "data"

    def access_token(self) -> str:
        if self._access_token:
            return self._access_token
        cached = self._load_cached_token()
        if cached:
            self._access_token = cached
            return cached
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }
        response = self._post("/oauth2/tokenP", payload, auth=False)
        self._access_token = response["access_token"]
        self._save_cached_token(response)
        return self._access_token

    def hashkey(self, payload: dict[str, Any]) -> str:
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }
        response = self._post("/uapi/hashkey", payload, auth=False, headers=headers)
        return response["HASH"]

    def order_domestic_stock(
        self,
        symbol: str,
        action: str,
        qty: int,
        price: int = 0,
        order_type: str = "01",
    ) -> dict[str, Any]:
        action = action.upper()
        if action not in {"BUY", "SELL"}:
            raise ValueError("action must be BUY or SELL")
        if self.config.env == "paper":
            tr_id = "VTTC0802U" if action == "BUY" else "VTTC0801U"
        else:
            tr_id = "TTTC0802U" if action == "BUY" else "TTTC0801U"

        payload = {
            "CANO": self.config.account_no,
            "ACNT_PRDT_CD": self.config.account_product_code,
            "PDNO": symbol,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        headers = self._auth_headers(tr_id)
        headers["hashkey"] = self.hashkey(payload)
        response = self._post("/uapi/domestic-stock/v1/trading/order-cash", payload, headers=headers)
        if str(response.get("rt_cd", "0")) != "0":
            message = response.get("msg1") or response.get("msg_cd") or response
            raise RuntimeError(f"KIS order rejected: {message}")
        return response

    def get_domestic_price(self, symbol: str) -> int:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }
        response = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            params,
            headers=self._auth_headers("FHKST01010100"),
        )
        if str(response.get("rt_cd", "0")) != "0":
            message = response.get("msg1") or response.get("msg_cd") or response
            raise RuntimeError(f"KIS price rejected: {message}")
        output = response.get("output") or {}
        price = output.get("stck_prpr")
        if not price:
            raise RuntimeError(f"KIS price response missing stck_prpr: {response}")
        return int(price)

    def get_domestic_balance(self) -> dict[str, Any]:
        tr_id = "VTTC8434R" if self.config.env == "paper" else "TTTC8434R"
        params = {
            "CANO": self.config.account_no,
            "ACNT_PRDT_CD": self.config.account_product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        response = self._get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            params,
            headers=self._auth_headers(tr_id),
        )
        if str(response.get("rt_cd", "0")) != "0":
            message = response.get("msg1") or response.get("msg_cd") or response
            raise RuntimeError(f"KIS balance rejected: {message}")
        return response

    def _auth_headers(self, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token()}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        auth: bool = True,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = headers or {"content-type": "application/json; charset=utf-8"}
        if auth:
            request_headers = {**request_headers, "authorization": f"Bearer {self.access_token()}"}
        data = json.dumps(payload).encode("utf-8")
        request = Request(self.config.base_url + path, data=data, headers=request_headers, method="POST")
        return self._open_json(request)

    def _get(
        self,
        path: str,
        params: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        url = self.config.base_url + path + "?" + urlencode(params)
        request = Request(url, headers=headers, method="GET")
        return self._open_json(request)

    def _open_json(self, request: Request) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                self._wait_for_rate_limit()
                with urlopen(request, timeout=20) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:800]
                if "EGW00201" in body and attempt < 3:
                    time.sleep(1.0 + attempt * 0.5)
                    last_error = exc
                    continue
                raise RuntimeError(f"KIS API HTTP {exc.code}: {body}") from exc
            except URLError as exc:
                raise RuntimeError(f"KIS API connection failed: {exc.reason}") from exc
        raise RuntimeError(f"KIS API rate limit retry failed: {last_error}")

    def _wait_for_rate_limit(self) -> None:
        global _KIS_LAST_REQUEST_AT
        with _KIS_LOCK:
            elapsed = time.monotonic() - _KIS_LAST_REQUEST_AT
            if elapsed < _KIS_MIN_INTERVAL_SECONDS:
                time.sleep(_KIS_MIN_INTERVAL_SECONDS - elapsed)
            _KIS_LAST_REQUEST_AT = time.monotonic()

    def _cache_path(self) -> Path:
        return self.token_cache_dir / f"kis_token_{self.config.env}.json"

    def _load_cached_token(self) -> str | None:
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if expires_at <= datetime.now() + timedelta(minutes=10):
                return None
            return payload["access_token"]
        except Exception:
            return None

    def _save_cached_token(self, response: dict[str, Any]) -> None:
        expires_in = int(response.get("expires_in", 60 * 60 * 24))
        expires_at = datetime.now() + timedelta(seconds=max(expires_in - 600, 60))
        payload = {
            "access_token": response["access_token"],
            "expires_at": expires_at.isoformat(timespec="seconds"),
        }
        self.token_cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
