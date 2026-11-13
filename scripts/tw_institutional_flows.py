import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.market.twse import TwseRepository
from stock_bot.report.webhook import DiscordWebhook


def main():
    parser = argparse.ArgumentParser(description="抓取證交所三大法人買賣金額日報")
    parser.add_argument("--date", type=date.fromisoformat, help="查詢日期，預設為台灣今天（YYYY-MM-DD）")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    day = args.date or datetime.now(ZoneInfo("Asia/Taipei")).date()
    try:
        rows = TwseRepository().fetch_institutional_flows(day)
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"三大法人日報抓取失敗：{exc}\n")
    print(json.dumps({
        "date": day.isoformat(),
        "status": "ok" if rows is not None else "no_data",
        "unit": "TWD",
        "rows": rows or [],
    }, ensure_ascii=False))
    if rows is None:
        return

    lines = [f"**三大法人買賣金額日報｜{day.isoformat()}**", "單位：新台幣元"]
    for row in rows:
        lines.append(
            f"**{row['name']}**｜買進 {row['buy_amount']:,}｜"
            f"賣出 {row['sell_amount']:,}｜買賣差額 {row['net_amount']:,}"
        )
    try:
        config = load_report_config(args.config)
        DiscordWebhook(config.webhook_url).send({
            "content": "\n".join(lines),
            "allowed_mentions": {"parse": []},
        })
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"三大法人日報發送失敗：{exc}\n")
    print("三大法人日報已發送")


if __name__ == "__main__":
    main()
