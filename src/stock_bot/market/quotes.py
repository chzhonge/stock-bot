import datetime
import re
from calendar import monthrange
from zoneinfo import ZoneInfo

import yfinance as yf


def parse_stock_query(text, aliases):
    text = text.strip()
    target = aliases.get(text.casefold())
    if target is not None:
        return [target], None

    parts = text.rsplit(maxsplit=1)
    period = None
    if len(parts) == 2:
        suffix = parts[-1].lower()
        if suffix in {"ytd", "max"} or re.fullmatch(r"[1-9][0-9]*(?:d|mo|y)", suffix):
            text, period = parts[0], suffix
        elif re.fullmatch(r"\d+(?:d|w|wk|m|mo|y)", suffix):
            raise ValueError(f"無效的區間 `{suffix}`，請使用正整數加 d、mo 或 y，例如 `14d`、`18mo`、`3y`")

    target = aliases.get(text.casefold())
    entries = [text] if target is not None else text.split(",") if "," in text else text.split()
    symbols = []
    for entry in entries:
        entry = entry.strip()
        symbol = aliases.get(entry.casefold(), entry).upper()
        if not re.fullmatch(r"(?:[0-9]{4,6}[A-Z]?(?:\.TW|\.TWO)?|[A-Z]{1,5}(?:[.-][A-Z]{1,2})?)", symbol):
            raise ValueError("請輸入股票代碼，例如 `0050 2y` 或 `0050 2330 2y`")
        if symbol not in symbols:
            symbols.append(symbol)
    if not 1 <= len(symbols) <= 5:
        raise ValueError("每次請輸入 1 至 5 個股票代碼")
    if period == "1d" and len(symbols) == 1:
        return symbols, None
    return symbols, period or ("1y" if len(symbols) > 1 else None)


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

    explicit_tw = re.fullmatch(r"\d{4,6}[A-Z]?\.(?:TW|TWO)", text)
    if explicit_tw:
        return text, [text]

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


def history_window(period, today):
    if period in {"ytd", "max"}:
        return {"period": period}

    count_text, unit = re.fullmatch(r"([1-9][0-9]*)(d|mo|y)", period).groups()
    try:
        count = int(count_text)
        if unit == "d":
            start = today - datetime.timedelta(days=count - 1)
        else:
            months = count * 12 if unit == "y" else count
            year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
            month += 1
            start = datetime.date(year, month, min(today.day, monthrange(year, month)[1]))
    except (OverflowError, ValueError):
        raise ValueError("查詢區間過長，請使用 `max` 查詢可取得的完整歷史。") from None
    return {"start": start.isoformat(), "end": (today + datetime.timedelta(days=1)).isoformat()}


def fetch_stock_history(user_input, period, timeout=10):
    code, candidates = resolve_ticker(user_input)
    today = datetime.datetime.now(ZoneInfo("Asia/Taipei")).date()
    window = history_window(period, today)
    for symbol in dict.fromkeys(candidates):
        data = yf.Ticker(symbol).history(
            **window, interval="1d", auto_adjust=True, actions=False, timeout=timeout,
        )
        if data.empty or "Close" not in data:
            continue
        closes = data["Close"].dropna()
        closes = closes[(closes > 0) & (closes < float("inf"))]
        closes.index = closes.index.tz_localize(None).normalize()
        closes = closes[~closes.index.duplicated(keep="last")].sort_index()
        if len(closes) >= 2:
            return code, closes
    raise ValueError(f"找不到 `{code}` 在 `{period}` 的足夠歷史資料。")


def align_history(history):
    if len(history) == 1:
        return history
    dates = next(iter(history.values())).index
    for series in history.values():
        dates = dates.intersection(series.index)
    if len(dates) < 2:
        raise ValueError("標的之間沒有足夠的共同交易日，請改用較長區間。")
    return {code: series.loc[dates] / series.loc[dates[0]] * 100 - 100 for code, series in history.items()}
