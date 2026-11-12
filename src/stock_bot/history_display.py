COMPARISON_METHOD = "首個共同交易日為 0% · Yahoo 原幣調整後收盤價（依資料調整分割與配息）"
COMPARISON_ADJUSTMENTS = (
    "股票與 ETF 的分割會換算成相同單位。配息按「除息前收盤價減配息」的價格估算再投入，"
    "未模擬發放日實際買回、稅費或匯率。價格型指數只反映指數點位變動。"
)


def history_heading(snapshot):
    series = snapshot["series"]
    code, first = next(iter(series.items()))
    dates = f"{first.index[0]:%Y/%m/%d} – {first.index[-1]:%Y/%m/%d}"
    if len(series) > 1:
        return "區間報酬率比較", f"{dates} · 共同交易日"
    label = snapshot.get("labels", {}).get(code, code)
    return f"{label} · 股價走勢", dates


def history_change(values):
    change = values.iloc[-1] - values.iloc[0]
    percent = change / values.iloc[0] * 100
    return change, f"{change:+,.2f}（{percent:+.2f}%）"
