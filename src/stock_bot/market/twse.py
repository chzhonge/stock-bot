import re
from datetime import datetime

import requests


URL = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
TURNOVER_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
FOREIGN_FLOWS_URL = "https://www.twse.com.tw/rwd/zh/fund/TWT38U"
FIELDS = ("單位名稱", "買進金額", "賣出金額", "買賣差額")
NO_DATA_STATUS = "很抱歉，沒有符合條件的資料"


class TwseRepository:
    def fetch_foreign_flows(self, day):
        query_date = day.strftime("%Y%m%d")
        try:
            response = requests.get(FOREIGN_FLOWS_URL, params={"date": query_date, "response": "json"}, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            raise RuntimeError("證交所外資買賣超查詢失敗") from None

        if not isinstance(payload, dict):
            raise ValueError("證交所外資買賣超格式異常")
        status = payload.get("stat")
        if isinstance(status, dict):
            status = status.get("stat")
        if isinstance(status, str) and status.strip().rstrip("!！。") in (
            NO_DATA_STATUS, "查詢日期大於可查詢最大日期，請重新查詢",
        ):
            return None
        if status != "OK":
            raise ValueError("證交所外資買賣超狀態異常")
        if payload.get("date") != query_date:
            return None

        fields, groups, data = (payload.get(key) for key in ("fields", "groups", "data"))
        if not all(isinstance(value, list) for value in (fields, groups, data)):
            raise ValueError("證交所外資買賣超缺少欄位或資料")
        try:
            code_index = fields.index("證券代號")
            name_index = fields.index("證券名稱")
            group = next(item for item in groups if item.get("title") == "外資及陸資(不含外資自營商)")
            start = group["start"]
            span = group["span"]
            if not isinstance(start, int) or not isinstance(span, int):
                raise ValueError
            end = start + span
            if not 0 <= start < end <= len(fields):
                raise ValueError
            net_index = fields.index("買賣超股數", start, end)
        except (AttributeError, KeyError, StopIteration, TypeError, ValueError):
            raise ValueError("證交所外資買賣超欄位不符") from None

        rows = []
        for row in data:
            if not isinstance(row, list) or len(row) != len(fields):
                raise ValueError("證交所外資買賣超資料列與欄位不符")
            code = str(row[code_index]).strip()
            name = str(row[name_index]).strip()
            net_shares = int(str(row[net_index]).replace(",", ""))
            rows.append((code, name, net_shares))
        return rows or None

    def fetch_market_turnover(self, day):
        try:
            response = requests.get(
                TURNOVER_URL,
                params={"date": day.strftime("%Y%m%d"), "response": "json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            raise RuntimeError("證交所市場成交資訊查詢失敗") from None

        if not isinstance(payload, dict):
            raise ValueError("證交所市場成交資訊格式異常")
        status = payload.get("stat")
        if isinstance(status, str) and status.strip().rstrip("!！。") == NO_DATA_STATUS:
            return None
        if status != "OK":
            raise ValueError("證交所市場成交資訊狀態異常")

        fields = payload.get("fields")
        data = payload.get("data")
        if not isinstance(fields, list) or any(fields.count(field) != 1 for field in ("日期", "成交金額")):
            raise ValueError("證交所市場成交資訊欄位不符")
        if not isinstance(data, list):
            raise ValueError("證交所市場成交資訊缺少資料列")
        date_index = fields.index("日期")
        amount_index = fields.index("成交金額")
        report_date = f"{day.year - 1911:03d}/{day:%m/%d}"
        for row in data:
            if not isinstance(row, list) or len(row) != len(fields):
                raise ValueError("證交所市場成交資訊資料列與欄位不符")
            if row[date_index] == report_date:
                turnover = int(str(row[amount_index]).replace(",", ""))
                return turnover if turnover > 0 else None
        return None

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
