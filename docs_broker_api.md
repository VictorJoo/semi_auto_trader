# 증권사 API 연결 가이드

## 권장 순서

1. 증권사 모의투자 API 신청
2. App Key, App Secret, 계좌번호를 `.env`에 저장
3. 토큰 발급 테스트
4. 잔고 조회 테스트
5. 1주 또는 최소 수량 모의 주문 테스트
6. 텔레그램 승인 주문을 모의 API로 연결
7. 실계좌 전환은 별도 환경변수와 이중 확인 버튼을 둔 뒤 진행

## 한국투자증권 Open API

한국투자증권 개발자센터에서 API를 신청합니다.

- 개발자센터: https://apiportal.koreainvestment.com/
- REST 방식은 계좌별 App Key/App Secret으로 접근 토큰을 발급받고 API를 호출합니다.
- WebSocket 방식은 실시간 시세 수신에 사용합니다.
- 2026년 현재 포털에 REST/웹소켓 유량 제한 공지가 있으므로 주문·시세 호출에는 속도 제한을 넣어야 합니다.

`.env` 예시:

```env
BROKER_PROVIDER=korea_investment
BROKER_ENV=paper
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCOUNT_NO=계좌번호_앞8자리
KIS_ACCOUNT_PRODUCT_CODE=01
```

모의투자 주문 테스트 예시:

```bash
python3 - <<'PY'
from pathlib import Path
from app.env import load_dotenv
from app.kis_api import KisApiClient, KisConfig

load_dotenv(Path(".env"))
client = KisApiClient(KisConfig.from_env())
print(client.access_token()[:12] + "...")
# 시장가 모의 매수 예시입니다. 실제 실행 전 종목과 수량을 꼭 확인하세요.
# print(client.order_domestic_stock("005930", "BUY", 1))
PY
```

접근 토큰은 `data/kis_token_paper.json`에 캐시됩니다. 토큰 발급 API를 짧은 시간에 반복 호출하면 거절될 수 있으므로, 실행이 실패하면 잠시 기다린 뒤 다시 시도하세요.

## LS증권 Open API

LS증권은 계좌 개설, xingAPI 신청, OPEN API 신청, 약관 동의 후 App Key/App Secret을 발급받아 접근 토큰을 발급하는 흐름입니다.

- 안내: https://openapi.ls-sec.co.kr/howto-use
- 모의투자 OPEN API는 별도 신청과 별도 App Key/Secret 발급이 필요합니다.
- 접근 토큰은 App Key/App Secret으로 발급하며 유효기간 이후 재발급해야 합니다.

## 현재 프로젝트에 붙이는 위치

- `app/broker.py`: 현재 모의 계좌 주문 처리
- `app/kis_api.py`: 한국투자증권 REST API 클라이언트 초안
- `app/core.py`: 대시보드/텔레그램 주문이 모이는 지점

다음 구현 단계에서는 `core.place_order()`에 `BROKER_PROVIDER`와 `BROKER_ENV`를 읽어, `paper`면 기존 모의 브로커를 쓰고 `korea_investment`면 `KisApiClient.order_domestic_stock()`을 호출하도록 연결하면 됩니다.
