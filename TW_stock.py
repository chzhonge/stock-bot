import datetime
import json
import os
import requests

from stock_bot.charts import build_taiex_chart
from stock_bot.market_data import fetch_intraday_snapshot


def get_taiex_snapshot():
    snapshot = fetch_intraday_snapshot("^TWII")
    if snapshot is None:
        raise ValueError("Yahoo Finance 無數據")
    return snapshot


def get_wantgoo_real_time(symbol):
    """
    獲取實時數據並計算漲跌
    """
    if symbol == "WTXP":
        snapshot = get_taiex_snapshot()
        return (
            snapshot["current_price"],
            snapshot["change_percent"],
            snapshot["change_amount"],
        )

    elif symbol == "00675L":
        # 證交所 API
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_00675L.tw"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data['msgArray']:
            item = data['msgArray'][0]
            # z 是當前成交價, y 是昨收價 (比 pz 更穩定)
            price_str = item.get('z', '-')
            prev_str = item.get('y', '-') 

            if price_str == '-' or prev_str == '-':
                # 如果盤後 z 變成 '-'，嘗試抓取最近一次成交價 'tv' 或 'o'
                price_str = item.get('o', prev_str) 

            price = float(price_str)
            prev = float(prev_str)
            
            change_amount = price - prev
            change_percent = (change_amount / prev) * 100 if prev != 0 else 0
            
            return price, change_percent, change_amount
    
    raise ValueError(f"無法獲取 {symbol} 的數據")

def get_wantgoo_fg():
    """從 CNN Fear & Greed Index 抓取美股市場情緒"""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://edition.cnn.com/",
        "Accept": "application/json",
    }

    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()

    fear_and_greed = data.get("fear_and_greed")
    if not fear_and_greed:
        raise ValueError("CNN Fear & Greed 無數據")

    value = round(float(fear_and_greed["score"]))
    classification_en = fear_and_greed["rating"]

    classifications = {
        "extreme fear": "極度恐懼",
        "fear": "恐懼",
        "neutral": "中立",
        "greed": "貪婪",
        "extreme greed": "極度貪婪",
    }
    classification = classifications.get(classification_en.lower(), classification_en)
    return value, classification

def send_discord_all():
    webhook_url = "https://discord.com/api/webhooks/1451566651765162036/z7-pOpZ0DKtodgdV8n9pGEFX-NVIohsqlSt4EQAL2LebGsOY9-7eO_Fvgy2zawcTXjc1"
    my_id = "302727629226639360"
    chart_path = None

    try:
        taiex = get_taiex_snapshot()
        tx_p = taiex["current_price"]
        tx_c_percent = taiex["change_percent"]
        tx_c_amount = taiex["change_amount"]
        chart_path = build_taiex_chart(taiex["session"], taiex["previous_close"])

        # 2. 抓取正二 (代號 00675L)
        st_p, st_c_percent, st_c_amount = get_wantgoo_real_time("00675L")
        print(f"富邦正2: {st_p:.2f} ({st_c_amount:+.2f})")  # 調試
        # 3. 抓取情緒
        fg_v, fg_t = get_wantgoo_fg()
        print(f"抓取到的 CNN Fear & Greed: {fg_v} ({fg_t})")  # 調試印出

        payload = {
            "content": f"<@{my_id}> 📈 實時行情報告",
            "embeds": [{
                "title": "台指走勢圖",
                "color": 3066993 if tx_c_amount >= 0 else 15158332,
                "image": {"url": "attachment://taiex_intraday.png"},
                "fields": [
                    {
                        "name": "📉 台指 (預估)", 
                        "value": f"**{tx_p:,.0f}** ({tx_c_amount:+.2f} / {tx_c_percent:+.2f}%)", 
                        "inline": True
                    },
                    {
                        "name": "📈 富邦正2 (00675L)", 
                        "value": f"**{st_p:.2f}** ({st_c_amount:+.2f} / {st_c_percent:+.2f}%)", 
                        "inline": True
                    },
                    {
                        "name": f"🌡️ 恐懼與貪婪 {fg_v} ({fg_t})", 
                        "value": "市場情緒同步中", 
                        "inline": False
                    }
                ]
            }]
        }
        with open(chart_path, "rb") as chart_file:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files={"file": ("taiex_intraday.png", chart_file, "image/png")},
                timeout=20,
            )
        response.raise_for_status()
        print("✅ 聯網發送成功！")

    except Exception as e:
        # 如果還是失敗，我們打印出完整的 Error 資訊來排查
        print(f"❌ 聯網抓取失敗: {e}")
    finally:
        if chart_path and os.path.exists(chart_path):
            os.remove(chart_path)

if __name__ == "__main__":
    # 檢查今天是不是上班日
    today = datetime.date.today()
    year = today.year
    month = f"{today.month:02d}"
    day = f"{today.day:02d}"
    url = f"https://api.pin-yi.me/taiwan-calendar/{year}/{month}/{day}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data:
            item = data[0]
            is_holiday = item['isHoliday']
            week = item['week']
            if not is_holiday and week not in ['Saturday', 'Sunday']:
                print("今天是上班日，執行程式")
                send_discord_all()
            else:
                print("今天不是上班日，跳過執行")
        else:
            print("無法獲取行事曆數據，預設執行")
            send_discord_all()
    except Exception as e:
        print(f"檢查上班日失敗: {e}，預設執行")

        send_discord_all()
