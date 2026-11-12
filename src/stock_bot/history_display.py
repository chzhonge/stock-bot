DIVIDEND_RETURN = "含息報酬"
PRICE_RETURN = "價格報酬"
COMPARISON_ADJUSTMENTS = (
    "股票與 ETF 的分割會換算成相同單位。配息按「除息前收盤價減配息」的價格估算再投入，"
    "未模擬發放日實際買回、稅費或匯率。價格型指數只反映指數點位變動。"
)
PRICE_COMPARISON_ADJUSTMENTS = (
    "股票與 ETF 的分割會換算成相同單位。配息、稅費和匯率皆不計入。價格型指數只反映指數點位變動。"
)


def history_price_label(snapshot):
    if all(code.startswith("^") for code in snapshot["series"]):
        return "指數點位"
    return "收盤價" if snapshot.get("price_only") else "調整後收盤價"


def comparison_method(snapshot):
    label = history_price_label(snapshot)
    return f"首個共同交易日為 0% · Yahoo 原幣{label}"


def history_heading(snapshot):
    series = snapshot["series"]
    code, first = next(iter(series.items()))
    dates = f"{first.index[0]:%Y/%m/%d} – {first.index[-1]:%Y/%m/%d}"
    mode = PRICE_RETURN if snapshot.get("price_only") else DIVIDEND_RETURN
    if all(symbol.startswith("^") for symbol in series):
        mode = "指數點位"
    if len(series) > 1:
        return f"區間報酬率比較 · {mode}", f"{dates} · 共同交易日"
    label = snapshot.get("labels", {}).get(code, code)
    return f"{label} · {mode}", dates


def history_change(values):
    change = values.iloc[-1] - values.iloc[0]
    percent = change / values.iloc[0] * 100
    return change, f"{change:+,.2f}（{percent:+.2f}%）"
