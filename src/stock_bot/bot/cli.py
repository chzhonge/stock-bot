import argparse
from pathlib import Path

from stock_bot.bot.repository import StockChartRepository
from stock_bot.bot.service import StockChartService
from stock_bot.config import load_config
from stock_bot.bot.discord_client import StockChartBot


def main():
    parser = argparse.ArgumentParser(description="Discord 股市小幫手")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        config.sample_file.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    repository = StockChartRepository(
        sample_file=config.sample_file,
        yahoo_url=config.yahoo_night_url,
        taifex_url=config.taifex_night_url,
        timeout=config.request_timeout_seconds,
    )
    service = StockChartService(
        repository,
        queue_size=config.queue_size,
        aliases=config.aliases,
    )
    StockChartBot(
        service,
        nickname=config.nickname,
        query_timeout_seconds=config.query_timeout_seconds,
    ).run(config.token)


if __name__ == "__main__":
    main()
