from stock_bot.market.quotes import fetch_stock_snapshot
from stock_bot.market.night import (
    fetch_night_snapshot,
    load_recent_night_samples,
    record_night_sample,
)


class StockChartRepository:
    def __init__(self, *, sample_file, yahoo_url, taifex_url, timeout):
        self.sample_file = sample_file
        self.yahoo_url = yahoo_url
        self.taifex_url = taifex_url
        self.timeout = timeout

    def fetch_stock(self, symbol):
        return fetch_stock_snapshot(symbol, self.timeout)

    def collect_night_quote(self, include_candles):
        snapshot = fetch_night_snapshot(self.yahoo_url, self.taifex_url, self.timeout)
        record_night_sample(snapshot, self.sample_file)
        if not include_candles:
            return snapshot, None
        return snapshot, load_recent_night_samples(self.sample_file)
