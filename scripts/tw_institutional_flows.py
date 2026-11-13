import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_bot.config import load_report_config
from stock_bot.market.twse import TwseRepository
from stock_bot.report.webhook import DiscordWebhook


def format_net_amount(amount):
    if amount > 0:
        direction = "🔴 買超"
    elif amount < 0:
        direction = "🟢 賣超"
    else:
        direction = "⚪ 買賣超"
    value = (Decimal(abs(amount)) / 100_000_000).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{direction} {value:,.2f} 億元"


def build_report(day, rows, turnover):
    by_name = {row["name"].strip().replace("（", "(").replace("）", ")"): row for row in rows}
    try:
        total = by_name["合計"]
        groups = (
            ("外資及陸資", by_name["外資及陸資(不含外資自營商)"]["net_amount"]),
            ("投信", by_name["投信"]["net_amount"]),
            ("自營商", by_name["自營商(自行買賣)"]["net_amount"] + by_name["自營商(避險)"]["net_amount"]),
        )
    except KeyError as exc:
        raise ValueError(f"證交所日報缺少必要欄位：{exc}") from None

    net = total["net_amount"]
    color = 0x95A5A6
    if net > 0:
        color = 0xE74C3C
    elif net < 0:
        color = 0x2ECC71
    ratio = "暫無資料"
    if turnover:
        value = Decimal(total["buy_amount"] + total["sell_amount"]) * 100 / (2 * turnover)
        ratio = f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}%"

    fields = [{"name": name, "value": format_net_amount(amount), "inline": True} for name, amount in groups]
    fields.extend([
        {"name": "三大法人合計", "value": format_net_amount(net), "inline": False},
        {"name": "法人成交比重（估算）", "value": ratio, "inline": False},
    ])
    return {
        "username": "股市小幫手",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": f"三大法人買賣超（{day:%Y/%m/%d}）",
            "color": color,
            "fields": fields,
            "footer": {"text": "資料來源：臺灣證券交易所"},
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="抓取證交所三大法人買賣金額日報")
    parser.add_argument("--date", type=date.fromisoformat, help="查詢日期，預設為台灣今天（YYYY-MM-DD）")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML 設定檔路徑")
    args = parser.parse_args()
    day = args.date or datetime.now(ZoneInfo("Asia/Taipei")).date()
    repository = TwseRepository()
    try:
        rows = repository.fetch_institutional_flows(day)
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

    try:
        turnover = repository.fetch_market_turnover(day)
    except (RuntimeError, ValueError) as exc:
        print(f"法人成交比重無法計算：{exc}", file=sys.stderr)
        turnover = None
    try:
        config = load_report_config(args.config)
        DiscordWebhook(config.webhook_url).send(build_report(day, rows, turnover))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"三大法人日報發送失敗：{exc}\n")
    print("三大法人日報已發送")


if __name__ == "__main__":
    main()
