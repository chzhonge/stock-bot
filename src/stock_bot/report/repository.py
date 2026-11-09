import requests

from stock_bot.market.quotes import fetch_intraday_snapshot


class MarketReportRepository:
    def __init__(self, sources):
        self.sources = sources

    def fetch_index(self, symbol):
        snapshot = fetch_intraday_snapshot(symbol)
        if snapshot is None:
            raise ValueError(f"Yahoo Finance 找不到 {symbol} 的盤中資料")
        return snapshot

    def fetch_quote(self, symbol, exchange):
        response = requests.get(
            self.sources.quote_url,
            params={"ex_ch": f"{exchange}_{symbol}.tw"},
            timeout=10,
        )
        response.raise_for_status()
        quotes = response.json().get("msgArray")
        if not quotes:
            raise ValueError(f"證交所找不到 {symbol} 的報價")

        quote = quotes[0]
        previous = quote.get("y", "-")
        price = quote.get("z", "-")
        if price == "-":
            price = quote.get("o", previous)
        try:
            price = float(price)
            previous = float(previous)
        except (TypeError, ValueError):
            raise ValueError(f"證交所缺少 {symbol} 的成交價或昨收") from None
        change = price - previous
        return price, change, change / previous * 100 if previous else 0

    def fetch_market_sentiment(self):
        """從 CNN Fear & Greed Index 抓取美股市場情緒"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": self.sources.sentiment_referer,
            "Accept": "application/json",
        }

        res = requests.get(self.sources.sentiment_url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        fear_and_greed = data.get("fear_and_greed")
        if not fear_and_greed:
            raise ValueError("CNN Fear & Greed 無數據")

        value = round(float(fear_and_greed["score"]))
        classification_en = fear_and_greed["rating"]

        classifications = {
            "extreme fear": "極度恐懼",
            "fear": "恐懼",
            "neutral": "中立",
            "greed": "貪婪",
            "extreme greed": "極度貪婪",
        }
        classification = classifications.get(classification_en.lower(), classification_en)
        return value, classification

    def is_workday(self, day):
        response = requests.get(f"{self.sources.calendar_url}/{day:%Y/%m/%d}", timeout=10)
        response.raise_for_status()
        days = response.json()
        if not days:
            raise ValueError("行事曆沒有回傳當日資料")
        entry = days[0]
        return not entry["isHoliday"] and entry["week"] not in {"Saturday", "Sunday"}
