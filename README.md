# Semi Auto Trader

주식 반자동 매매를 위한 모의투자 MVP입니다.

현재 포함된 것:

- CSV 기반 백테스트
- 이동평균/RSI 기반 매수·매도 신호 생성
- 신호별 매수·매도 이유 요약
- 모의 계좌 주문 실행
- React 대시보드 (실시간 차트 / 모의 매매 탭)
- 텔레그램 알림/명령 골격

## 구조

```
semi_auto_trader/
├── app/         # Python 백엔드 (HTTP API)
├── frontend/    # React + Vite 프론트엔드
└── data/        # 시세 CSV, 모의 포트폴리오 등의 사용자 데이터
```

백엔드는 API 전용이고, 프론트엔드는 별도의 Vite dev 서버로 실행합니다.

## 백엔드 실행

```bash
cd /Users/joo/Documents/Playground/semi_auto_trader
python3 -m app.server
```

API: `http://127.0.0.1:8765/api`

포트를 바꾸려면 인수 또는 환경변수로 지정할 수 있습니다.

```bash
python3 -m app.server 8766
# 또는
PORT=8766 python3 -m app.server
```

API 엔드포인트:

- `GET /api/health`
- `GET /api/snapshot`
- `GET /api/market?symbol=AAPL&period=day|week|month`
- `GET /api/refresh`
- `POST /api/approve` `{ "signal_id": "...", "qty": 1 }`
- `POST /api/order` `{ "symbol": "AAPL", "action": "BUY", "qty": 1 }`

## 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

기본 dev 주소: `http://127.0.0.1:5173`

프론트엔드는 Vite 프록시를 통해 `/api/*` 호출을 백엔드로 전달합니다. 백엔드 포트가 기본 `8765`가 아니라면 `frontend/.env.local`로 지정하면 됩니다.

```bash
# frontend/.env.local
VITE_API_TARGET=http://127.0.0.1:8766
```

`.env.local`은 git에 올라가지 않습니다. 환경변수로 일회성 변경도 가능합니다.

```bash
VITE_API_TARGET=http://127.0.0.1:8766 npm run dev
```

설정을 바꾼 뒤에는 Vite dev 서버를 한 번 재시작하세요 (Ctrl+C 후 `npm run dev`).

빌드:

```bash
npm run build
npm run preview
```

## CSV 데이터 형식

`data/prices.csv`가 있으면 해당 데이터를 사용합니다. 없으면 차트/시세는 빈 상태로 시작합니다.

```csv
date,symbol,close,volume
2026-01-02,AAPL,185.64,52000000
2026-01-03,AAPL,187.22,48000000
```

`volume` 열은 선택입니다.

## 텔레그램 설정

BotFather로 봇을 만든 뒤 환경변수를 설정합니다.

```bash
cp .env.example .env
# .env에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 입력
python3 -m app.telegram_bot
```

메시지가 오지 않으면 봇에게 `/start`를 보낸 뒤 아래 진단 명령을 실행하고, 출력되는 `recent_chats`의 `chat_id`를 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.

```bash
python3 -m app.telegram_diagnostics
```

지원 명령:

- `/status`
- `/signals`
- `/approve SIGNAL_ID`
- `/buy SYMBOL QTY`
- `/sell SYMBOL QTY`

텔레그램 명령은 현재 모의 계좌에만 반영됩니다.

## 증권사 API 연결

자세한 순서는 `docs_broker_api.md`를 참고하세요. 현재는 한국투자증권 REST API 클라이언트 초안을 `app/kis_api.py`에 넣어두었습니다.

실투자 보유 종목만 조회하고 주문은 모의투자로 유지하려면 `.env`를 이렇게 둡니다.

```env
BROKER_PROVIDER=korea_investment
BROKER_ENV=paper
KIS_ACCOUNT_ENV=live
```

실계좌용 App Key/App Secret이 모의투자와 다르면 `KIS_LIVE_APP_KEY`, `KIS_LIVE_APP_SECRET`, `KIS_LIVE_ACCOUNT_NO`를 추가로 설정하세요. `BROKER_ENV=live`는 실주문이 나갈 수 있으므로 조회만 원할 때는 바꾸지 마세요.

설정 점검:

```bash
python3 -m app.diagnostics
```
