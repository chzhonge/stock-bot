import logging
from pathlib import Path

from stock_bot.charts import build_taiex_chart


logger = logging.getLogger(__name__)
CHART_FILENAME = "market_intraday.png"


class MarketReportService:
    def __init__(self, repository, notifier):
        self.repository = repository
        self.notifier = notifier

    def run(self, config, day):
        try:
            if not self.repository.is_workday(day):
                return False
        except Exception:
            logger.warning("無法確認台灣上班日，依預設繼續發送")

        index = self.repository.fetch_index(config.index_symbol)
        fields = [{
            "name": f"📉 {config.index_label}",
            "value": (
                f"**{index['current_price']:,.0f}** "
                f"({index['change_amount']:+.2f} / {index['change_percent']:+.2f}%)"
            ),
            "inline": True,
        }]
        for quote in config.quotes:
            price, change, percent = self.repository.fetch_quote(quote.symbol, quote.exchange)
            fields.append({
                "name": f"📈 {quote.label} ({quote.symbol})",
                "value": f"**{price:.2f}** ({change:+.2f} / {percent:+.2f}%)",
                "inline": True,
            })

        score, rating = self.repository.fetch_market_sentiment()
        fields.append({
            "name": f"🌡️ 恐懼與貪婪 {score} ({rating})",
            "value": "市場情緒同步中",
            "inline": False,
        })
        mention = config.mention_user_id
        content = f"<@{mention}> 📈 實時行情報告" if mention else "📈 實時行情報告"
        payload = {
            "content": content,
            "allowed_mentions": {"parse": [], "users": [mention] if mention else []},
            "embeds": [{
                "title": f"{config.index_label}走勢圖",
                "color": 3066993 if index["change_amount"] >= 0 else 15158332,
                "image": {"url": f"attachment://{CHART_FILENAME}"},
                "fields": fields,
            }],
        }
        chart_path = Path(build_taiex_chart(
            index["session"],
            index["previous_close"],
            symbol=config.index_symbol,
            title=config.chart_title,
        ))
        try:
            self.notifier.send(payload, chart_path, CHART_FILENAME)
        finally:
            chart_path.unlink(missing_ok=True)
        return True
