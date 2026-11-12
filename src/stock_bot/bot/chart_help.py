import asyncio
import io
import logging

import discord
import pandas as pd

from stock_bot.history_display import COMPARISON_ADJUSTMENTS
from stock_bot.market.night import TAIWAN_TZ
from stock_bot.market.quotes import align_history


logger = logging.getLogger(__name__)

CHART_GUIDE = {
    "stock": (
        "單一標的盤中走勢",
        "`/stock-bot quote 代碼:0050` 或 `@機器人 0050`",
        "**怎麼讀線**　橫軸是市場當地時間，右側是價格。線尾圓點和數字是最新一筆價格。"
        "休市時可看右上角的交易日期，確認圖是哪一天的。\n\n"
        "**漲跌怎麼算**　藍色虛線 `Prev Close` 是前一交易日收盤價。"
        "圖中昨收 50 元、最新價 51 元，所以顯示 `+1.00（+2.00%）`。\n\n"
        "**其他數字**　`OPEN`、`HIGH`、`LOW` 分別是圖中第一筆、最高和最低價格。"
        "`Updated` 是最新一筆資料的時間。",
    ),
    "history": (
        "單一標的歷史走勢",
        "`/stock-bot quote 代碼:0050 區間:6mo` 或 `@機器人 0050 6mo`",
        "**怎麼讀線**　橫軸是日期，右側是價格。範例使用預設的含息報酬，右側顯示調整後收盤價。\n\n"
        "**漲跌怎麼算**　比較第一筆和最後一筆。"
        "圖中的調整後收盤價從 50 元到 55 元，所以區間漲跌是 `+5.00（+10.00%）`。\n\n"
        "**日期看哪裡**　標題下方顯示實際有資料的起訖日。若區間起點遇到休市，第一筆會落在有資料的交易日。\n\n"
        "**切換報酬**　`/stock-bot quote 代碼:0056 區間:1y 報酬:價格報酬` "
        "會顯示分割調整後的收盤價，區間漲跌不含配息。選報酬時請填寫歷史區間。",
    ),
    "comparison": (
        "多標的比較",
        "`/stock-bot compare 代碼:0050 sp500 區間:6mo` 或 `@機器人 0050 sp500 6mo`",
        "**從同一天開始算，誰漲得比較多？**　每條線代表一個標的。"
        "圖上只使用所有標的都有資料的日期。所有線都從第一個共同交易日的 `0%` 開始，"
        "右側刻度顯示比起點漲跌了多少。\n\n"
        "**怎麼看結果**　上方的同色數字是最後一個共同交易日的表現。"
        "圖中 0050 是 `+12%`，S&P 500 是 `+8%`，所以這段期間 0050 多漲了 **4 個百分點**。\n\n"
        "**含息報酬（預設）**　各標的使用 Yahoo 的原幣調整後收盤價。"
        f"{COMPARISON_ADJUSTMENTS}\n\n"
        "**價格報酬**　使用分割調整後的收盤價，配息不計入。"
        "可試 `/stock-bot compare 代碼:0050 0056 區間:1y 報酬:價格報酬`。\n\n"
        "**舉例**　0050 一拆四會把分割前的每單位價格除以四。"
        "假設 0056 昨收 40 元、配息 1 元，除息參考價就是 39 元。"
        "若當天收 39 元，含息報酬估算為 0%，價格報酬為 −2.5%。",
    ),
    "night": (
        "台指期夜盤",
        "`/stock-bot night` 或 `@機器人 夜盤`",
        "**怎麼讀線**　橫軸是台灣時間，可能跨過午夜。右側是台指期點數，線尾標出最新報價。\n\n"
        "**上方數字**　`OPEN`、`HIGH`、`LOW` 和 `VOLUME` 是夜盤的開盤、最高、最低與成交量。"
        "有前收資料時，藍色虛線 `Prev Close` 會標出參考值。\n\n"
        "**下方柱狀圖**　有分時成交量資料時，`5m vol` 會顯示各 5 分鐘時段的成交量。"
        "走勢資料不足時，機器人會顯示可取得的報價。",
    ),
}


def sample_chart(kind):
    if kind == "stock":
        times = pd.date_range("2026-01-05 09:00", periods=10, freq="30min", tz=TAIWAN_TZ)
        session = pd.Series([50.1, 50.4, 50.3, 50.9, 50.5, 51.2, 50.9, 51.1, 50.8, 51], index=times)
        return "stock", {"code": "0050", "name": "示範資料", "session": session, "previous_close": 50}, None

    if kind == "night":
        times = pd.date_range("2026-01-05 23:25", periods=10, freq="5min", tz=TAIWAN_TZ)
        prices = [19990, 20020, 19980, 20015, 20040, 20025, 20065, 20085, 20030, 20050]
        volumes = [150, 240, 200, 180, 230, 190, 300, 340, 290, 210]
        bars = [{"time": time, "close": price, "volume": volume} for time, price, volume in zip(times, prices, volumes)]
        snapshot = {
            "last_price": prices[-1], "previous_close": 20000, "change_amount": 50, "change_percent": 0.25,
            "open_price": prices[0], "high_price": max(prices), "low_price": min(prices),
            "volume": sum(volumes), "updated_at": times[-1],
        }
        return "night", snapshot, bars

    dates = pd.to_datetime([
        "2025-07-01", "2025-08-01", "2025-09-02", "2025-10-01", "2025-11-03", "2025-12-01", "2025-12-31",
    ])
    series = {"0050": pd.Series([50, 51, 50.5, 52, 54, 53, 55], index=dates)}
    labels = {"0050": "0050"}
    if kind == "comparison":
        series["0050"].iloc[-1] = 56
        series["^GSPC"] = pd.Series([6000, 6100, 6150, 6060, 6300, 6410, 6480], index=dates)
        labels["^GSPC"] = "S&P 500"
    return "history", {"series": align_history(series), "labels": labels, "period": "6mo"}, None


async def send_chart_help(send, user_id, service):
    embed = discord.Embed(
        title="圖表手冊",
        description="從下方選一種圖表，查看範例、讀法與查詢指令。所有範例使用固定示範資料。",
    )
    await send(embed=embed, view=ChartHelpView(user_id, service))


class ChartHelpView(discord.ui.View):
    def __init__(self, user_id, service):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.service = service
        self.selection_lock = asyncio.Lock()

    async def interaction_check(self, interaction):
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "只有開啟手冊的人可以切換。你可以用 `/stock-bot chart-help` 開啟自己的手冊。",
            ephemeral=True,
        )
        return False

    @discord.ui.select(
        placeholder="選擇圖表類型",
        options=[discord.SelectOption(label=title, value=kind) for kind, (title, _, _) in CHART_GUIDE.items()],
    )
    async def choose_chart(self, interaction, menu):
        kind = menu.values[0]
        await interaction.response.defer()
        async with self.selection_lock:
            try:
                image = await self.service.render(*sample_chart(kind))
            except Exception:
                logger.exception("圖表手冊範例繪製失敗")
                await interaction.followup.send("無法載入範例圖，請再選一次。", ephemeral=True)
                return

            title, example, description = CHART_GUIDE[kind]
            embed = discord.Embed(title=title, description=f"{description}\n\n**自己試試**　{example}")
            embed.set_footer(text="示範資料")
            embed.set_image(url="attachment://chart-example.png")
            with io.BytesIO(image) as buffer:
                attachment = discord.File(buffer, filename="chart-example.png", description=f"{title}示範圖")
                try:
                    await interaction.edit_original_response(embed=embed, attachments=[attachment], view=self)
                finally:
                    attachment.close()
