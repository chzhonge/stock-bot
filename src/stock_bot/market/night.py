import datetime
import json
import os
import re
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests


TAIWAN_TZ = ZoneInfo("Asia/Taipei")
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def night_session_start(timestamp):
    local = timestamp.astimezone(TAIWAN_TZ)
    start = local.replace(hour=15, minute=0, second=0, microsecond=0)
    if local.hour < 15:
        start -= datetime.timedelta(days=1)
    return start


def yahoo_chart_data(soup):
    for script in soup.find_all("script"):
        content = script.string or ""
        match = re.search(r'"libra"\s*:\s*\{\s*"WTX&"\s*:\s*', content)
        if match:
            try:
                chart, _ = json.JSONDecoder().raw_decode(content, match.end())
            except ValueError:
                continue
            if isinstance(chart, dict):
                return chart
    return {}


def yahoo_night_bars(chart, updated_at):
    start = night_session_start(updated_at)
    end = min(start + datetime.timedelta(hours=14), updated_at)
    try:
        timestamps = chart["timestamp"]
        quote = chart["indicators"]["quote"][0]
        closes, volumes = quote["close"], quote["volume"]
        if not all(isinstance(values, list) for values in (timestamps, closes, volumes)):
            return []
        if not len(timestamps) == len(closes) == len(volumes):
            return []
    except (KeyError, IndexError, TypeError):
        return []

    bars = {}
    first, last = start.timestamp(), end.timestamp()
    points = sorted(
        ((stamp, close, volume) for stamp, close, volume in zip(timestamps, closes, volumes)
         if isinstance(stamp, (int, float)) and first <= stamp <= last and isinstance(close, (int, float))),
        key=lambda point: point[0],
    )
    for stamp, close, volume in points:
        time = datetime.datetime.fromtimestamp(stamp, TAIWAN_TZ)
        # Yahoo labels minute bars by their closing time.
        slot = max(0, int((time - start).total_seconds() - 1) // 300)
        bucket = start + datetime.timedelta(minutes=slot * 5)
        bar = bars.setdefault(bucket, {"time": bucket, "close": close, "volume": None})
        bar["close"] = close
        if isinstance(volume, (int, float)) and volume >= 0:
            bar["volume"] = (bar["volume"] or 0) + volume
    return list(bars.values())

def fetch_taifex_night_snapshot(url, timeout):
    response = requests.get(url, timeout=timeout, headers=HTTP_HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    red_date = soup.find("p", style=lambda value: value and "color: #cc0000" in value.lower())
    report_date = red_date.get_text(" ", strip=True).replace("日期：", "").strip() if red_date else ""

    session_text = ""
    for text_node in soup.stripped_strings:
        if "15:00~次日05:00" in text_node and "盤後交易時段行情表" in text_node:
            session_text = text_node
            break

    rows = soup.find_all("tr")
    first_tx_cells = None
    for row in rows:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) >= 15 and cells[0] == "TX":
            first_tx_cells = cells
            break

    if not first_tx_cells:
        raise ValueError("期交所夜盤資料頁沒有找到 TX 近月資料")

    def parse_number(value):
        clean = value.strip().replace(",", "").replace("%", "")
        direction = clean[:1]
        clean = clean.lstrip("▲▼").strip()
        if clean == "-":
            return None
        number = float(clean)
        return -abs(number) if direction == "▼" else number

    return {
        "report_date": report_date,
        "session_text": session_text,
        "contract": first_tx_cells[1],
        "open_price": parse_number(first_tx_cells[2]),
        "high_price": parse_number(first_tx_cells[3]),
        "low_price": parse_number(first_tx_cells[4]),
        "last_price": parse_number(first_tx_cells[5]),
        "change_amount": parse_number(first_tx_cells[6]),
        "change_percent": parse_number(first_tx_cells[7]),
        "volume": parse_number(first_tx_cells[8]),
        "settlement_price": parse_number(first_tx_cells[9]),
        "open_interest": parse_number(first_tx_cells[10]),
        "best_bid": parse_number(first_tx_cells[11]),
        "best_ask": parse_number(first_tx_cells[12]),
    }


def fetch_yahoo_night_snapshot(url, timeout):
    response = requests.get(url, timeout=timeout, headers=HTTP_HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text("\n", strip=True)

    def parse_number(value):
        clean = value.strip().replace(",", "").replace("%", "")
        return float(clean)

    def extract(pattern, label, cast=float, required=True):
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            if required:
                raise ValueError(f"Yahoo 夜盤頁面缺少欄位: {label}")
            return None
        return cast(match.group(1))

    timestamp_match = re.search(r"資料時間[：:]\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})", text)
    if not timestamp_match:
        timestamp_match = re.search(r"(?:開盤|收盤)\s*\|\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})\s*更新", text)
    if not timestamp_match:
        raise ValueError("Yahoo 夜盤頁面缺少時間戳")

    timestamp_text = timestamp_match.group(1)
    timestamp = datetime.datetime.strptime(timestamp_text, "%Y/%m/%d %H:%M").replace(tzinfo=TAIWAN_TZ)
    last_price = extract(r"成交\s+([0-9,]+(?:\.[0-9]+)?)", "last", parse_number)
    previous_close = extract(r"昨收\s+([0-9,]+(?:\.[0-9]+)?)", "previous close", parse_number)
    change_amount = last_price - previous_close
    chart = yahoo_chart_data(soup)
    # The visible Yahoo total can be abbreviated (for example, 15 for 15,457).
    volume = None
    quote = chart.get("quote")
    meta = chart.get("meta")
    if isinstance(quote, dict) and isinstance(meta, dict) and meta.get("regularMarketTime") == int(timestamp.timestamp()):
        try:
            if float(quote["price"]) == last_price:
                volume = parse_number(str(quote["volume"]))
        except (KeyError, TypeError, ValueError):
            pass

    return {
        "report_date": timestamp.strftime("%Y/%m/%d"),
        "session_text": "Yahoo WTX& current-day session",
        "contract": "WTX&",
        "open_price": extract(r"開盤\s+([0-9,]+(?:\.[0-9]+)?)", "open", parse_number),
        "high_price": extract(r"最高\s+([0-9,]+(?:\.[0-9]+)?)", "high", parse_number),
        "low_price": extract(r"最低\s+([0-9,]+(?:\.[0-9]+)?)", "low", parse_number),
        "last_price": last_price,
        "change_amount": change_amount,
        "change_percent": change_amount / previous_close * 100 if previous_close else None,
        "volume": volume,
        "settlement_price": None,
        "open_interest": extract(r"未平倉\s+([0-9,]+)", "open interest", parse_number, required=False),
        "best_bid": extract(r"買價\s+([0-9,]+(?:\.[0-9]+)?)", "best bid", parse_number, required=False),
        "best_ask": extract(r"賣價\s+([0-9,]+(?:\.[0-9]+)?)", "best ask", parse_number, required=False),
        "source": "yahoo",
        "updated_at": timestamp,
        "previous_close": previous_close,
        "average_price": None,
        "history": yahoo_night_bars(chart, timestamp),
    }


def fetch_night_snapshot(yahoo_url, taifex_url, timeout):
    try:
        return fetch_yahoo_night_snapshot(yahoo_url, timeout)
    except Exception as yahoo_exc:
        print(f"Yahoo 夜盤抓取失敗，改用期交所: {yahoo_exc}")
        snapshot = fetch_taifex_night_snapshot(taifex_url, timeout)
        snapshot["source"] = "taifex"
        snapshot["updated_at"] = datetime.datetime.now(TAIWAN_TZ)
        return snapshot


def record_night_sample(snapshot, sample_file):
    updated_at = snapshot.get("updated_at") or datetime.datetime.now(TAIWAN_TZ)
    sample = {
        "ts": updated_at.isoformat(),
        "report_date": snapshot["report_date"],
        "contract": snapshot["contract"],
        "source": snapshot.get("source"),
        "last_price": snapshot["last_price"],
        "volume": snapshot["volume"],
    }
    with open(sample_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(sample, ensure_ascii=True) + "\n")


def load_recent_night_samples(sample_file):
    if not sample_file.exists():
        return []

    cutoff = datetime.datetime.now(TAIWAN_TZ) - datetime.timedelta(hours=16)
    samples = []
    with open(sample_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                item["dt"] = datetime.datetime.fromisoformat(item["ts"])
            except (KeyError, TypeError, ValueError):
                continue
            if item["dt"].utcoffset() is not None and item["dt"] >= cutoff and item.get("last_price") is not None:
                samples.append(item)

    samples.sort(key=lambda item: item["dt"])
    return samples


def prune_night_samples(sample_file):
    if not sample_file.exists():
        return

    samples = load_recent_night_samples(sample_file)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=sample_file.parent, prefix=".night-samples-", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            for sample in samples:
                sample.pop("dt")
                temp_file.write(json.dumps(sample, ensure_ascii=True) + "\n")
        os.replace(temp_path, sample_file)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def build_night_candles(samples, minutes=5):
    buckets = {}
    for sample in samples:
        dt = sample["dt"]
        rounded_minute = (dt.minute // minutes) * minutes
        bucket_key = dt.replace(minute=rounded_minute, second=0, microsecond=0)
        buckets.setdefault(bucket_key, []).append(sample)

    candles = []
    for bucket_time in sorted(buckets):
        bucket_samples = buckets[bucket_time]
        prices = [float(item["last_price"]) for item in bucket_samples]
        volumes = [item.get("volume") for item in bucket_samples if item.get("volume") is not None]
        volume = None
        if len(volumes) >= 2:
            volume = max(0, int(volumes[-1] - volumes[0]))
        candles.append(
            {
                "time": bucket_time,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": volume,
            }
        )
    return candles
