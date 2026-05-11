from __future__ import annotations

from datetime import datetime
from statistics import mean

from .models import PriceBar, Signal


def moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-window - 1 : -1], values[-window:]):
        delta = current - previous
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def generate_signal(symbol: str, bars: list[PriceBar], buying_power: float) -> Signal | None:
    if len(bars) < 35:
        return None

    closes = [bar.close for bar in bars]
    price = closes[-1]
    short_ma = moving_average(closes, 5)
    long_ma = moving_average(closes, 20)
    previous_short = moving_average(closes[:-1], 5)
    previous_long = moving_average(closes[:-1], 20)
    momentum = (price / closes[-6] - 1) * 100
    current_rsi = rsi(closes)

    if None in (short_ma, long_ma, previous_short, previous_long, current_rsi):
        return None

    buy_reasons: list[str] = []
    sell_reasons: list[str] = []
    buy_score = 0.0
    sell_score = 0.0

    if previous_short <= previous_long and short_ma > long_ma:
        buy_score += 0.25
        buy_reasons.append("5일 이동평균이 20일 이동평균을 상향 돌파했습니다.")
    if short_ma > long_ma and momentum > 2:
        buy_score += 0.15
        buy_reasons.append(f"최근 5거래일 수익률이 {momentum:.1f}%로 단기 모멘텀이 강합니다.")
    if current_rsi < 35 and short_ma >= long_ma * 0.98:
        buy_score += 0.1
        buy_reasons.append(f"RSI가 {current_rsi:.1f}로 과매도권에 가까워 반등 여지가 있습니다.")

    if previous_short >= previous_long and short_ma < long_ma:
        sell_score += 0.25
        sell_reasons.append("5일 이동평균이 20일 이동평균을 하향 이탈했습니다.")
    if momentum < -2.5:
        sell_score += 0.15
        sell_reasons.append(f"최근 5거래일 수익률이 {momentum:.1f}%로 단기 약세가 뚜렷합니다.")
    if current_rsi > 72:
        sell_score += 0.1
        sell_reasons.append(f"RSI가 {current_rsi:.1f}로 과열권에 가까워 차익실현 위험이 있습니다.")

    if buy_score == 0 and sell_score == 0:
        return None
    if buy_score >= sell_score:
        action = "BUY"
        confidence = 0.45 + buy_score
        reasons = buy_reasons
    else:
        action = "SELL"
        confidence = 0.45 + sell_score
        reasons = sell_reasons

    risk_budget = buying_power * 0.12
    suggested_qty = max(1, int(risk_budget // price))
    signal_id = f"{symbol}-{bars[-1].date.isoformat()}-{action}"
    return Signal(
        id=signal_id,
        created_at=datetime.now(),
        symbol=symbol,
        action=action,
        price=price,
        confidence=min(confidence, 0.95),
        reasons=reasons[:3],
        suggested_qty=suggested_qty,
    )
