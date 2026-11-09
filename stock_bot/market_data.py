import re

import yfinance as yf


def fetch_intraday_snapshot(symbol, *, timeout=10, minimum_points=1, include_name=False):
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="2d", interval="5m", timeout=timeout)
    if data.empty:
        return None

    closes = data["Close"].dropna()
    if closes.empty:
        return None

    latest_ts = closes.index[-1]
    session = closes.loc[closes.index.date == latest_ts.date()]
    if len(session) < minimum_points:
        return None

    previous = closes.loc[closes.index.date < latest_ts.date()]
    previous_close = float(previous.iloc[-1]) if not previous.empty else None
    info = None
    if previous_close is None:
        fast_info = getattr(ticker, "fast_info", {}) or {}
        previous_close = fast_info.get("previous_close")
    if previous_close is None:
        info = ticker.info
        previous_close = info.get("previousClose")
    if previous_close is None:
        previous_close = float(session.iloc[0])

    name = None
    if include_name:
        if info is None:
            info = ticker.info
        name = info.get("longName") or info.get("shortName")

    current_price = float(session.iloc[-1])
    change_amount = current_price - previous_close
    return {
        "symbol": symbol,
        "name": name,
        "session": session,
        "session_date": latest_ts.date(),
        "latest_ts": latest_ts,
        "previous_close": float(previous_close),
        "current_price": current_price,
        "change_amount": change_amount,
        "change_percent": change_amount / previous_close * 100 if previous_close else 0,
        "open_price": float(session.iloc[0]),
        "high_price": float(session.max()),
        "low_price": float(session.min()),
    }


def resolve_ticker(user_input):
    text = user_input.strip().upper()
    if not text:
        raise ValueError("請在提及機器人後面加上股票代碼，例如 `2330` 或 `AAPL`。")

    tw_match = re.search(r"\b\d{4,6}[A-Z]?\b", text)
    if tw_match:
        code = tw_match.group(0)
        return code, [f"{code}.TW", f"{code}.TWO"]

    us_match = re.search(r"\b[A-Z]{1,5}(?:[.-][A-Z]{1,2})?\b", text)
    if us_match:
        code = us_match.group(0)
        return code, [code.replace(".", "-"), code]

    raise ValueError(
        "目前支援台股與美股代碼，例如 `2330`、`0050`、`00631L`、`AAPL`、`TSLA`、`VOO`、`BRK.B`。"
    )


def fetch_stock_snapshot(user_input, timeout=10):
    code, candidates = resolve_ticker(user_input)

    for symbol in candidates:
        snapshot = fetch_intraday_snapshot(symbol, timeout=timeout, minimum_points=2, include_name=True)
        if snapshot is None:
            continue
        snapshot["code"] = code
        snapshot["name"] = snapshot["name"] or code
        return snapshot

    raise ValueError(f"找不到代碼 `{code}` 的盤中資料，請確認代碼是否正確或是否為交易時段。")
