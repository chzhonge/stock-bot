import asyncio
import datetime
import io
import logging
import re
from contextlib import nullcontext
from functools import partial

import discord
from discord import app_commands
from discord.ext import tasks

from stock_bot.bot.chart_help import send_chart_help
from stock_bot.charts import trend_color
from stock_bot.history_display import COMPARISON_ADJUSTMENTS, COMPARISON_METHOD, history_change, history_heading
from stock_bot.market.night import TAIWAN_TZ
from stock_bot.market.quotes import INDEX_SYMBOL


logger = logging.getLogger(__name__)

INDEX_NAMES = {
    "^TWII": "台灣加權指數",
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq 綜合指數",
    "^DJI": "道瓊工業平均指數",
    "^SOX": "費城半導體指數",
}


def help_embed():
    return discord.Embed(
        title="股票機器人｜查詢說明",
        description=(
            "輸入 `/stock-bot` 後選擇指令，也可以在頻道提及機器人查詢。\n\n"
            "**盤中走勢**\n"
            "`/stock-bot quote 代碼:2330` 或 `@機器人 2330`\n"
            "查看最新交易日的盤中圖。\n\n"
            "**歷史走勢**\n"
            "`/stock-bot quote 代碼:AAPL 區間:2y` 或 `@機器人 AAPL 2y`\n"
            "查看單一標的的歷史走勢。\n\n"
            "**指數走勢**\n"
            "`/stock-bot index 指數:大盤 區間:6mo` 或 `@機器人 大盤 6mo`\n"
            "可用名稱、別名或代碼搜尋，例如大盤、sp500、費半。\n\n"
            "**多檔比較**\n"
            "`/stock-bot compare 代碼:0050 2330 區間:6mo` 或 `@機器人 0050 2330 6mo`\n"
            "用空格分隔 2 至 5 個標的。省略區間時預設比較近 1 年。\n\n"
            "**台指期夜盤**\n"
            "`/stock-bot night` 或 `@機器人 夜盤`\n"
            "查看夜盤報價與可取得的走勢圖。\n\n"
            "**區間寫法**\n"
            "`14d`（14 天）、`6mo`（6 個月）、`2y`（2 年）、"
            "`ytd`（今年以來）、`max`（最長可用區間）\n\n"
            "**圖表手冊**\n"
            "`/stock-bot chart-help` 或 `@機器人 chart-help`，查看圖表範例與讀法。"
        ),
    )


class StockCommands(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="stock-bot", description="查詢股票走勢、多檔報酬率與台指期夜盤")
        self.bot = bot

    @app_commands.command(description="查看股票機器人的查詢說明")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=help_embed(), ephemeral=True)

    @app_commands.command(name="chart-help", description="查看四種圖表的範例與讀法")
    async def chart_help(self, interaction: discord.Interaction):
        send = partial(interaction.response.send_message, ephemeral=True)
        await send_chart_help(send, interaction.user.id, self.bot.service)

    @app_commands.command(description="查詢單一標的的盤中或歷史走勢")
    @app_commands.rename(symbol="代碼", period="區間")
    @app_commands.describe(symbol="股票、ETF 或指數代碼，例如 0050", period="例如 6mo、2y 或 ytd，留空查盤中")
    async def quote(self, interaction: discord.Interaction, symbol: str, period: str | None = None):
        await self.bot.run_slash_query(interaction, "quote", symbol, period)

    @app_commands.command(description="查詢單一指數的盤中或歷史走勢")
    @app_commands.rename(symbol="指數", period="區間")
    @app_commands.describe(symbol="搜尋指數名稱、別名或代碼", period="例如 6mo、2y 或 ytd，留空查盤中")
    async def index(self, interaction: discord.Interaction, symbol: str, period: str | None = None):
        await self.bot.run_slash_query(interaction, "index", symbol, period)

    @index.autocomplete("symbol")
    async def index_autocomplete(self, interaction: discord.Interaction, current: str):
        aliases_by_code = {}
        for alias, target in self.bot.service.aliases.items():
            code = target.upper()
            if re.fullmatch(INDEX_SYMBOL, code):
                aliases_by_code.setdefault(code, []).append(alias)

        query = current.strip().casefold()
        choices = []
        for code in dict.fromkeys((*INDEX_NAMES, *aliases_by_code)):
            if code not in aliases_by_code:
                continue
            name = INDEX_NAMES.get(code, code)
            aliases = aliases_by_code[code]
            if not any(query in term.casefold() for term in (name, code, *aliases)):
                continue
            label = f"{name}（{code}）" if name != code else code
            matching_alias = next(
                (alias for alias in aliases if alias.casefold() != name.casefold() and query in alias.casefold()),
                None,
            )
            if matching_alias:
                label += f" · {matching_alias}"
            choices.append(app_commands.Choice(name=label[:100], value=code))
            if len(choices) == 25:
                break
        return choices

    @app_commands.command(description="比較 2 至 5 個標的的報酬率")
    @app_commands.rename(symbols="代碼", period="區間")
    @app_commands.describe(symbols="以空格分隔代碼，例如 0050 2330", period="例如 6mo、2y 或 ytd，留空比較近 1 年")
    async def compare(self, interaction: discord.Interaction, symbols: str, period: str | None = None):
        await self.bot.run_slash_query(interaction, "compare", symbols, period)

    @app_commands.command(description="查看台指期夜盤報價與走勢")
    async def night(self, interaction: discord.Interaction):
        await self.bot.run_slash_query(interaction, "night")


class StockChartBot(discord.Client):
    def __init__(self, service, *, nickname, query_timeout_seconds):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.service = service
        self.nickname = nickname
        self.query_timeout_seconds = query_timeout_seconds
        self.command_tree = app_commands.CommandTree(self)
        self.command_tree.add_command(StockCommands(self))

    async def setup_hook(self):
        await self.service.start()
        try:
            await self.command_tree.sync()
        except discord.HTTPException:
            logger.exception("Discord 斜線指令同步失敗")

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
        reply = partial(message.reply, mention_author=False)
        if user_input.casefold() == "help":
            await reply(embed=help_embed())
            return

        if user_input.casefold() == "chart-help":
            await send_chart_help(reply, message.author.id, self.service)
            return

        await self.run_query(reply, user_input, typing=message.channel.typing)

    async def run_slash_query(self, interaction, command, user_input="", period=None):
        await interaction.response.defer(thinking=True)
        await self.run_query(interaction.followup.send, user_input, command=command, period=period)

    async def run_query(self, reply, user_input, *, command=None, period=None, typing=nullcontext):
        deadline = asyncio.get_running_loop().time() + self.query_timeout_seconds
        try:
            with self.service.reserve_query():
                result = self.service.enqueue(user_input, deadline, command=command, period=period)
                await self.handle_query(reply, result, deadline, typing)
        except asyncio.QueueFull:
            await reply("目前查詢較多，請稍後再試。")

    async def handle_query(self, reply, result, deadline, typing):
        try:
            async with typing():
                async with asyncio.timeout_at(deadline):
                    reply_type, snapshot, candles = await result
                image = await self.service.render(reply_type, snapshot, candles)
                await self.reply_with_chart(reply, reply_type, snapshot, image)
        except TimeoutError:
            await reply("行情查詢逾時，請稍後再試。")
        except ValueError as exc:
            await reply(f"查詢失敗：{exc}")
        except Exception:
            logger.exception("行情查詢或回覆失敗")
            await reply("查詢失敗，請稍後再試。")
        finally:
            if not result.done():
                result.cancel()

    async def reply_with_chart(self, reply, reply_type, snapshot, image):
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
                lines.extend([COMPARISON_METHOD, COMPARISON_ADJUSTMENTS])
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
                await reply(embed=embed, file=attachment)
            finally:
                attachment.close()
