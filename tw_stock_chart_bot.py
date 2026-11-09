import argparse
import asyncio
import datetime
import io
import logging
from pathlib import Path

import discord
from discord.ext import tasks
from yfinance.exceptions import YFRateLimitError

from stock_bot.charts import build_stock_chart, build_taifex_night_candles_chart, build_taifex_night_chart
from stock_bot.config import load_config
from stock_bot.market_data import fetch_stock_snapshot
from stock_bot.night_market import (
    TAIWAN_TZ,
    build_night_candles,
    fetch_night_snapshot,
    is_night_session_query,
    load_recent_night_samples,
    record_night_sample,
)


logger = logging.getLogger(__name__)
YAHOO_COOLDOWN_SECONDS = 30


class StockChartBot(discord.Client):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.quote_queue = asyncio.Queue(maxsize=config.queue_size)
        self.quote_worker = None
        self.night_lock = asyncio.Lock()
        self.chart_lock = asyncio.Lock()

    async def setup_hook(self):
        self.quote_worker = asyncio.create_task(self.process_quotes())

    async def close(self):
        self.night_sampler.cancel()
        if self.quote_worker is not None:
            self.quote_worker.cancel()
            await asyncio.gather(self.quote_worker, return_exceptions=True)
        while not self.quote_queue.empty():
            _, _, result = self.quote_queue.get_nowait()
            result.cancel()
            self.quote_queue.task_done()
        await super().close()

    async def process_quotes(self):
        loop = asyncio.get_running_loop()
        yahoo_retry_at = 0.0
        while True:
            user_input, deadline, result = await self.quote_queue.get()
            try:
                if result.done() or loop.time() >= deadline:
                    continue

                if is_night_session_query(user_input):
                    data, candles = await self.collect_night_quote(include_candles=True)
                    reply = ("night", data, candles)
                else:
                    if loop.time() < yahoo_retry_at:
                        raise ValueError("Yahoo Finance 暫時限制查詢，請稍後再試")
                    data = await asyncio.to_thread(
                        fetch_stock_snapshot, user_input, self.config.request_timeout_seconds
                    )
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
            snapshot = await asyncio.to_thread(fetch_night_snapshot, self.config.request_timeout_seconds)
            await asyncio.to_thread(record_night_sample, snapshot, self.config.sample_file)
            if not include_candles:
                return snapshot, None
            samples = await asyncio.to_thread(load_recent_night_samples, self.config.sample_file)
            return snapshot, build_night_candles(samples)

    async def on_ready(self):
        display_name = self.config.nickname
        for guild in self.guilds:
            member = guild.me
            if member and member.nick != display_name:
                try:
                    await member.edit(nick=display_name)
                except discord.HTTPException:
                    logger.warning("更新伺服器暱稱失敗，伺服器 %s", guild.id, exc_info=True)
        logger.info("%s 已上線，等待股票代碼查詢", display_name)
        if not self.night_sampler.is_running():
            self.night_sampler.start()

    @tasks.loop(minutes=1)
    async def night_sampler(self):
        now = datetime.datetime.now(TAIWAN_TZ)
        minute_of_day = now.hour * 60 + now.minute
        if 5 * 60 < minute_of_day < 15 * 60:
            return
        try:
            snapshot, _ = await self.collect_night_quote()
            logger.info("夜盤樣本已記錄，%s %s", snapshot["contract"], snapshot["last_price"])
        except Exception:
            logger.exception("夜盤樣本記錄失敗")

    async def on_message(self, message):
        if self.user is None or message.author == self.user or self.user not in message.mentions:
            return

        user_input = message.content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()
        loop = asyncio.get_running_loop()
        result = loop.create_future()
        deadline = loop.time() + self.config.query_timeout_seconds
        try:
            self.quote_queue.put_nowait((user_input, deadline, result))
        except asyncio.QueueFull:
            await message.reply("目前查詢較多，請稍後再試。", mention_author=False)
            return

        try:
            async with message.channel.typing():
                async with asyncio.timeout_at(deadline):
                    reply_type, snapshot, candles = await result
                async with self.chart_lock:
                    image = await asyncio.to_thread(render_chart, reply_type, snapshot, candles)
                await self.reply_with_chart(message, reply_type, snapshot, image)
        except TimeoutError:
            await message.reply("行情查詢逾時，請稍後再試。", mention_author=False)
        except ValueError as exc:
            await message.reply(f"查詢失敗：{exc}", mention_author=False)
        except Exception:
            logger.exception("行情查詢或回覆失敗")
            await message.reply("查詢失敗，請稍後再試。", mention_author=False)
        finally:
            if not result.done():
                result.cancel()

    async def reply_with_chart(self, message, reply_type, snapshot, image):
        if reply_type == "night":
            file_name = "tx_night_session.png"
            source_url = snapshot.get("source_url", "").lower()
            if "yahoo" in source_url:
                source_label = "Yahoo WTX&"
            elif "wantgoo" in source_url:
                source_label = "WantGoo WTXP&"
            else:
                source_label = "TAIFEX 期交所夜盤行情"
            embed = discord.Embed(
                title=f"TX 夜盤 {snapshot['contract']}",
                description=(
                    f"最新 `{snapshot['last_price']:,.0f}`  "
                    f"漲跌 `{snapshot['change_amount']:+.0f}`  "
                    f"漲跌幅 `{snapshot['change_percent']:+.2f}%`"
                ),
                color=0x138A5C if snapshot["change_amount"] >= 0 else 0xD64045,
            )
            embed.set_footer(text=f"資料來源 {source_label}")
        else:
            file_name = f"{snapshot['code']}_intraday.png"
            embed = discord.Embed(
                title=f"{snapshot['code']} {snapshot['name']}",
                description=(
                    f"現價 `{snapshot['current_price']:,.2f}`  "
                    f"漲跌 `{snapshot['change_amount']:+.2f}`  "
                    f"漲跌幅 `{snapshot['change_percent']:+.2f}%`"
                ),
                color=0x138A5C if snapshot["change_amount"] >= 0 else 0xD64045,
            )
            embed.set_footer(text=f"資料來源 Yahoo Finance | 代碼 {snapshot['symbol']}")
        embed.set_image(url=f"attachment://{file_name}")

        await message.reply(
            embed=embed,
            file=discord.File(io.BytesIO(image), filename=file_name),
            mention_author=False,
        )


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


def main():
    parser = argparse.ArgumentParser(description="Discord 股市小幫手")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        config.sample_file.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    StockChartBot(config).run(config.token)


if __name__ == "__main__":
    main()
