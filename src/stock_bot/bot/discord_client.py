import asyncio
import datetime
import io
import logging

import discord
from discord.ext import tasks

from stock_bot.market.night import TAIWAN_TZ


logger = logging.getLogger(__name__)


class StockChartBot(discord.Client):
    def __init__(self, service, *, nickname, query_timeout_seconds):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.service = service
        self.nickname = nickname
        self.query_timeout_seconds = query_timeout_seconds

    async def setup_hook(self):
        await self.service.start()

    async def close(self):
        self.night_sampler.cancel()
        await self.service.close()
        await super().close()

    async def on_ready(self):
        display_name = self.nickname
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
            snapshot, _ = await self.service.collect_night_quote()
            logger.info("夜盤樣本已記錄，%s %s", snapshot["contract"], snapshot["last_price"])
        except Exception:
            logger.exception("夜盤樣本記錄失敗")

    async def on_message(self, message):
        if self.user is None or message.author == self.user or self.user not in message.mentions:
            return

        user_input = message.content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.query_timeout_seconds
        try:
            result = self.service.enqueue(user_input, deadline)
        except asyncio.QueueFull:
            await message.reply("目前查詢較多，請稍後再試。", mention_author=False)
            return

        try:
            async with message.channel.typing():
                async with asyncio.timeout_at(deadline):
                    reply_type, snapshot, candles = await result
                image = await self.service.render(reply_type, snapshot, candles)
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
            source_label = "Yahoo WTX&" if snapshot.get("source") == "yahoo" else "TAIFEX 期交所夜盤行情"
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
