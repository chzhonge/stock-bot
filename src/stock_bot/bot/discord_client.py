import asyncio
import datetime
import io
import logging

import discord
from discord.ext import tasks

from stock_bot.charts import trend_color
from stock_bot.history_display import COMPARISON_METHOD, history_change, history_heading
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
            with self.service.reserve_query():
                result = self.service.enqueue(user_input, deadline)
                await self.handle_query(message, result, deadline)
        except asyncio.QueueFull:
            await message.reply("目前查詢較多，請稍後再試。", mention_author=False)

    async def handle_query(self, message, result, deadline):
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
            change = snapshot["change_amount"]
            percent = snapshot["change_percent"]
            trend = f"漲跌 `{change:+.0f}`  漲跌幅 `{percent:+.2f}%`" if change is not None and percent is not None else "漲跌資料未提供"
            embed = discord.Embed(
                title=f"TX 夜盤 {snapshot['contract']}",
                description=f"最新 `{snapshot['last_price']:,.0f}`  {trend}",
                color=discord.Colour.from_str(trend_color(change)),
            )
        elif reply_type == "history":
            series = snapshot["series"]
            labels = snapshot.get("labels", {})
            comparison = len(series) > 1
            file_name = "stock_comparison.png" if comparison else "stock_history.png"
            title, dates = history_heading(snapshot)
            lines = [dates]
            if comparison:
                lines.extend(
                    f"**{labels.get(code, code)}** `{values.iloc[-1]:+.2f}%`"
                    for code, values in series.items()
                )
                color = discord.Colour.from_str(trend_color(None))
            else:
                values = next(iter(series.values()))
                change, change_text = history_change(values)
                lines.extend([
                    f"最新調整後收盤價 `{values.iloc[-1]:,.2f}`",
                    f"區間漲跌 `{change_text}`",
                ])
                color = discord.Colour.from_str(trend_color(change))
            lines.append(f"查詢區間 `{snapshot['period']}`")
            if comparison:
                lines.append(COMPARISON_METHOD)
            embed = discord.Embed(title=title, description="\n".join(lines), color=color)
        else:
            file_name = f"{snapshot['code']}_intraday.png"
            embed = discord.Embed(
                title=f"{snapshot['code']} {snapshot['name']}",
                description=(
                    f"交易日期 `{snapshot['session_date']:%Y-%m-%d}`（市場當地）\n"
                    f"現價 `{snapshot['current_price']:,.2f}`  "
                    f"漲跌 `{snapshot['change_amount']:+.2f}`  "
                    f"漲跌幅 `{snapshot['change_percent']:+.2f}%`"
                ),
                color=discord.Colour.from_str(trend_color(snapshot["change_amount"])),
            )
        embed.set_image(url=f"attachment://{file_name}")

        with io.BytesIO(image) as buffer:
            attachment = discord.File(buffer, filename=file_name)
            try:
                await message.reply(embed=embed, file=attachment, mention_author=False)
            finally:
                attachment.close()
