COMPARISON_METHOD = "以首個共同交易日為 0%，按各標的原幣調整後收盤價計算"


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
