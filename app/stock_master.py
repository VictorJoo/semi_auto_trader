from __future__ import annotations

import json
import time
import zipfile
from io import BytesIO
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = ROOT / "data" / "stock_master.json"
_CACHE_TTL_SECONDS = 60 * 60 * 24

_MASTER_FILES = {
    "KOSPI": {
        "url": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
        "filename": "kospi_code.mst",
        "suffix_width": 228,
    },
    "KOSDAQ": {
        "url": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
        "filename": "kosdaq_code.mst",
        "suffix_width": 222,
    },
}


@dataclass(frozen=True)
class StockMasterEntry:
    code: str
    name: str
    market: str


def load_stock_master(
    cache_path: Path = DEFAULT_CACHE_PATH, *, refresh: bool = False
) -> list[StockMasterEntry]:
    if not refresh:
        cached = _load_cached_master(cache_path)
        if cached:
            return cached

    entries = download_stock_master()
    if entries:
        _save_master_cache(cache_path, entries)
        return entries

    return _load_cached_master(cache_path, ignore_ttl=True)


def download_stock_master() -> list[StockMasterEntry]:
    entries: list[StockMasterEntry] = []
    for market, meta in _MASTER_FILES.items():
        entries.extend(
            _download_and_parse_market(
                market=market,
                url=meta["url"],
                filename=meta["filename"],
                suffix_width=meta["suffix_width"],
            )
        )
    entries_by_code = {entry.code: entry for entry in entries}
    return sorted(entries_by_code.values(), key=lambda entry: (entry.name, entry.code))


def _download_and_parse_market(
    *, market: str, url: str, filename: str, suffix_width: int
) -> list[StockMasterEntry]:
    with urlopen(url, timeout=20) as response:
        archive = response.read()

    entries: list[StockMasterEntry] = []
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        raw = zip_file.read(filename).decode("cp949")

    for row in raw.splitlines():
        if not row:
            continue
        head = row[: len(row) - suffix_width]
        code = head[:9].strip()
        name = head[21:].strip()
        if len(code) != 6 or not code.isdigit() or not name:
            continue
        entries.append(StockMasterEntry(code=code, name=name, market=market))
    return entries


def _load_cached_master(
    cache_path: Path, *, ignore_ttl: bool = False
) -> list[StockMasterEntry]:
    if not cache_path.exists():
        return []
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not ignore_ttl:
        created_at = float(payload.get("created_at") or 0)
        if time.time() - created_at > _CACHE_TTL_SECONDS:
            return []

    entries: list[StockMasterEntry] = []
    for item in payload.get("entries") or []:
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        market = str(item.get("market") or "").strip()
        if len(code) == 6 and code.isdigit() and name:
            entries.append(StockMasterEntry(code=code, name=name, market=market))
    return entries


def _save_master_cache(cache_path: Path, entries: list[StockMasterEntry]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": time.time(),
        "source": "korea_investment_master_files",
        "entries": [asdict(entry) for entry in entries],
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
