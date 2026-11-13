import argparse
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.market.tw_names import fetch_listed_stock_and_etf_codes
from stock_bot.market.twse import TwseRepository
from stock_bot.report.webhook import DiscordWebhook


def ranking_field(title, rows):
    lines = [
        f"{rank}. **{code} {name}**　{Decimal(abs(shares)) / 1000:,.3f} 張"
        for rank, (code, name, shares) in enumerate(rows, 1)
    ]
    return {"name": title, "value": "\n".join(lines) or "無", "inline": False}


def build_report(day, rows, eligible_codes):
    eligible = [row for row in rows if row[0] in eligible_codes]
    if not eligible:
        raise ValueError("外資買賣超資料與上市證券名冊無相符標的")
    buys = sorted((row for row in eligible if row[2] > 0), key=lambda row: (-row[2], row[0]))[:10]
    sells = sorted((row for row in eligible if row[2] < 0), key=lambda row: (row[2], row[0]))[:10]
    return {
        "username": "股市小幫手",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": f"上市外資買賣超排行（{day:%Y/%m/%d}）",
            "fields": [ranking_field("🔴 買超前 10", buys), ranking_field("🟢 賣超前 10", sells)],
            "footer": {"text": "臺灣證券交易所｜上市股票與 ETF｜不含外資自營商"},
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="發送上市外資買賣超排行榜")
    parser.add_argument("--date", type=date.fromisoformat, help="查詢日期，預設為台灣今天（YYYY-MM-DD）")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    day = args.date or datetime.now(ZoneInfo("Asia/Taipei")).date()

    try:
        rows = TwseRepository().fetch_foreign_flows(day)
        if rows is None:
            print(f"{day} 外資買賣超排行榜暫無資料")
            return
        payload = build_report(day, rows, fetch_listed_stock_and_etf_codes())
        config = load_report_config(args.config)
        DiscordWebhook(config.webhook_url).send(payload)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"外資買賣超排行榜執行失敗：{exc}\n")
    print(f"{day} 外資買賣超排行榜已發送")


if __name__ == "__main__":
    main()
