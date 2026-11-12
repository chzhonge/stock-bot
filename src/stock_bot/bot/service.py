import asyncio
from contextlib import contextmanager

from yfinance.exceptions import YFRateLimitError

from stock_bot.charts import build_history_chart, build_night_chart, build_stock_chart
from stock_bot.market.night import build_night_candles
from stock_bot.market.quotes import align_history, parse_stock_query, parse_stock_selection


YAHOO_COOLDOWN_SECONDS = 30


class StockChartService:
    def __init__(self, repository, *, queue_size, aliases):
        self.repository = repository
        self.aliases = aliases
        self.quote_queue = asyncio.Queue(maxsize=queue_size)
        self.max_in_flight = queue_size + 1
        self.in_flight = 0
        self.quote_worker = None
        self.night_lock = asyncio.Lock()
        self.chart_lock = asyncio.Lock()

    @contextmanager
    def reserve_query(self):
        if self.in_flight >= self.max_in_flight:
            raise asyncio.QueueFull
        self.in_flight += 1
        try:
            yield
        finally:
            self.in_flight -= 1

    def enqueue(self, user_input, deadline, *, command=None, period=None):
        result = asyncio.get_running_loop().create_future()
        self.quote_queue.put_nowait((user_input, deadline, result, command, period))
        return result

    async def start(self):
        self.quote_worker = asyncio.create_task(self.process_quotes())

    async def close(self):
        if self.quote_worker is not None:
            self.quote_worker.cancel()
            await asyncio.gather(self.quote_worker, return_exceptions=True)
        while not self.quote_queue.empty():
            _, _, result, _, _ = self.quote_queue.get_nowait()
            result.cancel()
            self.quote_queue.task_done()

    async def process_quotes(self):
        loop = asyncio.get_running_loop()
        yahoo_retry_at = 0.0
        while True:
            user_input, deadline, result, command, requested_period = await self.quote_queue.get()
            try:
                if result.done() or loop.time() >= deadline:
                    continue

                target = self.aliases.get(user_input.strip().casefold())
                if command == "night" or (command is None and target is not None and target.casefold() == "night"):
                    data, candles = await self.collect_night_quote(include_candles=True)
                    reply = ("night", data, candles)
                else:
                    if loop.time() < yahoo_retry_at:
                        raise ValueError("Yahoo Finance 暫時限制查詢，請稍後再試")
                    if command is None:
                        symbols, period = parse_stock_query(user_input, self.aliases)
                    else:
                        symbols, period = parse_stock_selection(user_input, self.aliases, requested_period)
                        if command == "quote" and len(symbols) != 1:
                            raise ValueError("請輸入一個標的。若要比較多檔，請使用 `/stock-bot compare`。")
                        if command == "compare" and len(symbols) < 2:
                            raise ValueError("請輸入至少兩個不同的標的，例如 `0050 2330`。")
                    if period is None:
                        data = await asyncio.to_thread(self.repository.fetch_stock, symbols[0])
                        reply = ("stock", data, None)
                    else:
                        history = {}
                        labels = {}
                        for symbol in symbols:
                            remaining = deadline - loop.time()
                            if result.done() or remaining <= 0:
                                raise TimeoutError
                            code, series, name = await asyncio.to_thread(
                                self.repository.fetch_history, symbol, period, remaining,
                            )
                            history[code] = series
                            labels[code] = f"{code} {name}" if name else code
                        reply = ("history", {
                            "period": period, "series": align_history(history), "labels": labels,
                        }, None)
                if not result.done():
                    result.set_result(reply)
            except asyncio.CancelledError:
                result.cancel()
                raise
            except YFRateLimitError:
                yahoo_retry_at = loop.time() + YAHOO_COOLDOWN_SECONDS
                if not result.done():
                    result.set_exception(ValueError("Yahoo Finance 暫時限制查詢，請稍後再試"))
            except Exception as exc:
                if not result.done():
                    result.set_exception(exc)
            finally:
                self.quote_queue.task_done()

    async def collect_night_quote(self, *, include_candles=False):
        async with self.night_lock:
            snapshot, samples = await asyncio.to_thread(self.repository.collect_night_quote, include_candles)
        if samples is None:
            return snapshot, None
        return snapshot, snapshot.get("history") or build_night_candles(samples)

    async def render(self, reply_type, snapshot, candles):
        async with self.chart_lock:
            return await asyncio.to_thread(render_chart, reply_type, snapshot, candles)


def render_chart(reply_type, snapshot, candles):
    if reply_type == "stock":
        return build_stock_chart(snapshot)
    if reply_type == "history":
        return build_history_chart(snapshot)
    return build_night_chart(snapshot, candles)
