import datetime
import time

from stock_bot.market.quotes import fetch_stock_history, fetch_stock_snapshot
from stock_bot.market.night import (
    fetch_night_snapshot,
    load_recent_night_samples,
    night_session_start,
    prune_night_samples,
    record_night_sample,
)


class StockChartRepository:
    def __init__(self, *, sample_file, yahoo_url, taifex_url, timeout):
        self.sample_file = sample_file
        self.yahoo_url = yahoo_url
        self.taifex_url = taifex_url
        self.timeout = timeout
        self.next_prune_at = 0.0

    def fetch_stock(self, symbol):
        return fetch_stock_snapshot(symbol, self.timeout)

    def fetch_history(self, symbol, period, remaining):
        return fetch_stock_history(symbol, period, min(self.timeout, remaining))

    def collect_night_quote(self, include_candles):
        now = time.monotonic()
        if now >= self.next_prune_at:
            prune_night_samples(self.sample_file)
            self.next_prune_at = now + 3600
        snapshot = fetch_night_snapshot(self.yahoo_url, self.taifex_url, self.timeout)
        record_night_sample(snapshot, self.sample_file)
        if not include_candles:
            return snapshot, None
        if snapshot.get("history"):
            return snapshot, []
        start = night_session_start(snapshot["updated_at"])
        samples = [
            item for item in load_recent_night_samples(self.sample_file)
            if start <= item["dt"] <= start + datetime.timedelta(hours=14)
            and item.get("contract") == snapshot["contract"]
            and item.get("source") in (None, snapshot["source"])
        ]
        return snapshot, samples
