import re
from datetime import datetime

import requests


URL = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
FIELDS = ("單位名稱", "買進金額", "賣出金額", "買賣差額")
NO_DATA_STATUS = "很抱歉，沒有符合條件的資料"


class TwseRepository:
    def fetch_institutional_flows(self, day):
        query_date = day.strftime("%Y%m%d")
        try:
            response = requests.get(
                URL,
                params={"type": "day", "dayDate": query_date, "response": "json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(str(exc)) from exc
        if not isinstance(payload, dict):
            raise ValueError("證交所回應格式異常")

        status = payload.get("stat")
        if isinstance(status, str) and status.strip().rstrip("!！。") == NO_DATA_STATUS:
            return None
        if status != "OK":
            raise ValueError(f"證交所查詢狀態異常：{status!r}")

        report_date = payload.get("date")
        if not isinstance(report_date, str) or not re.fullmatch(r"[0-9]{8}", report_date):
            raise ValueError("證交所回應缺少有效的報表日期")
        actual_day = datetime.strptime(report_date, "%Y%m%d").date()
        if actual_day != day:
            return None

        fields = payload.get("fields")
        data = payload.get("data")
        if not isinstance(fields, list) or any(fields.count(field) != 1 for field in FIELDS):
            raise ValueError("證交所報表欄位不符")
        if not isinstance(data, list) or not data:
            raise ValueError("證交所報表缺少資料列")

        rows = []
        for values in data:
            if not isinstance(values, list) or len(values) != len(fields):
                raise ValueError("證交所報表資料列與欄位不符")
            row = dict(zip(fields, values))
            name = row["單位名稱"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("證交所報表缺少單位名稱")
            rows.append({
                "name": name,
                "buy_amount": int(str(row["買進金額"]).replace(",", "")),
                "sell_amount": int(str(row["賣出金額"]).replace(",", "")),
                "net_amount": int(str(row["買賣差額"]).replace(",", "")),
            })
        return rows
