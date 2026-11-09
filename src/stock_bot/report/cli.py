import argparse
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.report.webhook import DiscordWebhook
from stock_bot.report.repository import MarketReportRepository
from stock_bot.report.service import MarketReportService


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
        sent = service.run(config, today)
    except Exception as exc:
        parser.exit(1, f"快報執行失敗：{exc}\n")
    print("快報已發送" if sent else "今天不是上班日，跳過發送")


if __name__ == "__main__":
    main()
