import argparse
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from stock_bot.market.twse import TwseRepository


def main():
    parser = argparse.ArgumentParser(description="抓取證交所三大法人買賣金額日報")
    parser.add_argument("--date", type=date.fromisoformat, help="查詢日期，預設為台灣今天（YYYY-MM-DD）")
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


if __name__ == "__main__":
    main()
