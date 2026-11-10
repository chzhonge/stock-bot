import logging
from dataclasses import dataclass

from stock_bot.charts import build_taiex_chart, trend_color


logger = logging.getLogger(__name__)
CHART_FILENAME = "market_intraday.png"


@dataclass(frozen=True)
class WatchlistEntry:
    symbol: str
    label: str
    exchange: str


class MarketReportService:
    def __init__(self, repository, notifier):
        self.repository = repository
        self.notifier = notifier

    def run(self, *, day, index_symbol, index_label, chart_title, watchlist: tuple[WatchlistEntry, ...], mention_user_id):
        if len(watchlist) > 23:
            raise ValueError("快報最多可列出 23 檔股票")

        try:
            if not self.repository.is_workday(day):
                return False
        except Exception:
            logger.warning("無法確認台灣上班日，依預設繼續發送")

        index = self.repository.fetch_index(index_symbol)
        fields = [{
            "name": f"📉 {index_label}",
            "value": (
                f"**{index['current_price']:,.0f}** "
                f"({index['change_amount']:+.2f} / {index['change_percent']:+.2f}%)"
            ),
            "inline": True,
        }]
        for item in watchlist:
            price, change, percent = self.repository.fetch_quote(item.symbol, item.exchange)
            fields.append({
                "name": f"📈 {item.label} ({item.symbol})",
                "value": f"**{price:.2f}** ({change:+.2f} / {percent:+.2f}%)",
                "inline": True,
            })

        score, rating = self.repository.fetch_market_sentiment()
        fields.append({
            "name": f"🌡️ 恐懼與貪婪 {score} ({rating})",
            "value": "市場情緒同步中",
            "inline": False,
        })
        content = f"<@{mention_user_id}> 📈 實時行情報告" if mention_user_id else "📈 實時行情報告"
        payload = {
            "content": content,
            "allowed_mentions": {"parse": [], "users": [mention_user_id] if mention_user_id else []},
            "embeds": [{
                "title": f"{index_label}走勢圖",
                "color": int(trend_color(index["change_amount"])[1:], 16),
                "image": {"url": f"attachment://{CHART_FILENAME}"},
                "fields": fields,
            }],
        }
        chart = build_taiex_chart(
            index["session"],
            index["previous_close"],
            title=chart_title,
        )
        self.notifier.send(payload, chart, CHART_FILENAME)
        return True
