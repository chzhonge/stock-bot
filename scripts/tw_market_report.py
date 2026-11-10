import argparse
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.report.webhook import DiscordWebhook
from stock_bot.report.repository import MarketReportRepository
from stock_bot.report.service import MarketReportService, WatchlistEntry


INDEX_SYMBOL = "^TWII"
INDEX_LABEL = "台指 (預估)"
CHART_TITLE = "TAIEX Session Trend"

WATCHLIST = (
    WatchlistEntry(symbol="00675L", label="富邦正2", exchange="tse"),
)


def main():
    parser = argparse.ArgumentParser(description="發送台股市場快報")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    try:
        config = load_report_config(args.config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    service = MarketReportService(
        repository=MarketReportRepository(config.sources),
        notifier=DiscordWebhook(config.webhook_url),
    )
    today = datetime.datetime.now(ZoneInfo("Asia/Taipei")).date()
    try:
        sent = service.run(
            day=today,
            index_symbol=INDEX_SYMBOL,
            index_label=INDEX_LABEL,
            chart_title=CHART_TITLE,
            watchlist=WATCHLIST,
            mention_user_id=config.mention_user_id,
        )
    except Exception as exc:
        parser.exit(1, f"快報執行失敗：{exc}\n")
    print("快報已發送" if sent else "今天不是上班日，跳過發送")


if __name__ == "__main__":
    main()
