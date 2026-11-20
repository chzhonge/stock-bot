import argparse
import json
import sys
import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.market.twse import TwseRepository
from stock_bot.report.webhook import DiscordWebhook


def format_amount(thousands):
    value = (Decimal(thousands) / 100_000).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:,.2f} 億元"


def balance_field(title, row, formatter):
    change = row["今日餘額"] - row["前日餘額"]
    direction = "增加" if change > 0 else "減少" if change < 0 else "持平"
    return {
        "name": title,
        "value": f"**{formatter(row['今日餘額'])}**\n較前日{direction} {formatter(abs(change))}",
        "inline": True,
    }


def format_units(value):
    return f"{value:,} 交易單位"


def build_report(day, rows):
    financing, short = rows["financing_amount"], rows["short_units"]
    return {
        "username": "日報-股市小幫手",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": f"上市融資融券日報｜{day:%Y/%m/%d}",
            "color": 0x3498DB,
            "fields": [
                balance_field("融資餘額", financing, format_amount),
                balance_field("融券餘額", short, format_units),
                {
                    "name": "融資交易明細",
                    "value": "\n".join((
                        f"買進　{format_amount(financing['買進'])}",
                        f"賣出　{format_amount(financing['賣出'])}",
                        f"現金償還　{format_amount(financing['現金(券)償還'])}",
                    )),
                    "inline": False,
                },
                {
                    "name": "融券交易明細",
                    "value": "\n".join((
                        f"賣出　{format_units(short['賣出'])}",
                        f"買進回補　{format_units(short['買進'])}",
                        f"現券償還　{format_units(short['現金(券)償還'])}",
                    )),
                    "inline": False,
                },
            ],
            "footer": {"text": (
                "資料來源：臺灣證券交易所｜增減＝本表今日餘額－前日餘額\n"
                "今日餘額仍可能於次一交易日調整"
            )},
        }],
    }


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必須為正整數")
    return number


def fetch_with_retries(repository, day, attempts, retry_interval):
    for attempt in range(1, attempts + 1):
        try:
            rows = repository.fetch_margin_balances(day)
        except RuntimeError as exc:
            if attempt == attempts:
                raise
            print(f"{day} 融資融券查詢失敗：{exc}", file=sys.stderr, flush=True)
        else:
            if rows is not None or attempt == attempts:
                return rows
        print(
            f"{day} 融資融券尚未取得（{attempt}/{attempts}），{retry_interval} 秒後重試",
            file=sys.stderr, flush=True,
        )
        time.sleep(retry_interval)


def main():
    parser = argparse.ArgumentParser(description="抓取並發送上市融資融券日報")
    parser.add_argument("--date", type=date.fromisoformat, help="查詢日期，預設為台灣今天（YYYY-MM-DD）")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    parser.add_argument("--dry-run", action="store_true", help="輸出資料與卡片 JSON，不讀取設定或發送 Discord")
    parser.add_argument("--attempts", type=positive_int, default=1, help="查詢次數，預設 1")
    parser.add_argument("--retry-interval", type=positive_int, default=900, help="重試間隔秒數，預設 900")
    args = parser.parse_args()
    # Keep the target date fixed even if a retry crosses midnight.
    day = args.date or datetime.now(ZoneInfo("Asia/Taipei")).date()

    try:
        rows = fetch_with_retries(TwseRepository(), day, args.attempts, args.retry_interval)
        payload = build_report(day, rows) if rows is not None else None
        print(json.dumps({
            "date": day.isoformat(),
            "status": "ok" if rows is not None else "no_data",
            "units": {"financing_amount": "TWD_thousands", "financing_units": "交易單位", "short_units": "交易單位"},
            "rows": rows,
            "discord": payload,
        }, ensure_ascii=False))
        if rows is None or args.dry_run:
            return
        config = load_report_config(args.config)
        # Retry only data retrieval: an ambiguous webhook failure must not trigger a duplicate send.
        DiscordWebhook(config.webhook_url).send(payload)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"融資融券日報執行失敗：{exc}\n")
    print(f"{day} 融資融券日報已發送")


if __name__ == "__main__":
    main()
