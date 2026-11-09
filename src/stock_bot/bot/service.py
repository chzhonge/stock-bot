import asyncio
from pathlib import Path

from yfinance.exceptions import YFRateLimitError

from stock_bot.charts import build_stock_chart, build_taifex_night_candles_chart, build_taifex_night_chart
from stock_bot.market.night import build_night_candles


YAHOO_COOLDOWN_SECONDS = 30


class StockChartService:
    def __init__(self, repository, *, queue_size, night_aliases):
        self.repository = repository
        self.night_aliases = night_aliases
        self.quote_queue = asyncio.Queue(maxsize=queue_size)
        self.quote_worker = None
        self.night_lock = asyncio.Lock()
        self.chart_lock = asyncio.Lock()

    def enqueue(self, user_input, deadline):
        result = asyncio.get_running_loop().create_future()
        self.quote_queue.put_nowait((user_input, deadline, result))
        return result

    async def start(self):
        self.quote_worker = asyncio.create_task(self.process_quotes())

    async def close(self):
        if self.quote_worker is not None:
            self.quote_worker.cancel()
            await asyncio.gather(self.quote_worker, return_exceptions=True)
        while not self.quote_queue.empty():
            _, _, result = self.quote_queue.get_nowait()
            result.cancel()
            self.quote_queue.task_done()

    async def process_quotes(self):
        loop = asyncio.get_running_loop()
        yahoo_retry_at = 0.0
        while True:
            user_input, deadline, result = await self.quote_queue.get()
            try:
                if result.done() or loop.time() >= deadline:
                    continue

                if user_input.strip().lower() in self.night_aliases:
                    data, candles = await self.collect_night_quote(include_candles=True)
                    reply = ("night", data, candles)
                else:
                    if loop.time() < yahoo_retry_at:
                        raise ValueError("Yahoo Finance 暫時限制查詢，請稍後再試")
                    data = await asyncio.to_thread(self.repository.fetch_stock, user_input)
                    reply = ("stock", data, None)
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
        return snapshot, build_night_candles(samples) if samples is not None else None

    async def render(self, reply_type, snapshot, candles):
        async with self.chart_lock:
            return await asyncio.to_thread(render_chart, reply_type, snapshot, candles)


def render_chart(reply_type, snapshot, candles):
    if reply_type == "stock":
        image_path = build_stock_chart(snapshot)
    elif len(candles) >= 2:
        image_path = build_taifex_night_candles_chart(snapshot, candles)
    else:
        image_path = build_taifex_night_chart(snapshot)

    path = Path(image_path)
    try:
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
