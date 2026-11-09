import datetime
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def build_taiex_chart(session, previous_close):
    """生成較完整的台指盤中走勢圖。"""
    closes = [float(value) for value in session.tolist()]
    if len(closes) < 2:
        raise ValueError("台指資料點不足，無法生成圖表")

    timestamps = list(session.index)
    latest_price = closes[-1]
    session_high = max(closes)
    session_low = min(closes)
    session_open = closes[0]
    change_amount = latest_price - previous_close
    change_percent = (change_amount / previous_close) * 100 if previous_close else 0
    line_color = "#d64045" if change_amount < 0 else "#138a5c"
    fill_color = "#f6d9dc" if change_amount < 0 else "#d7f0e4"

    fig = plt.figure(figsize=(12.6, 7.2), dpi=160, facecolor="#f3f6fb")
    ax = fig.add_axes([0.07, 0.14, 0.88, 0.68])
    ax.set_facecolor("#ffffff")

    ax.plot(timestamps, closes, color=line_color, linewidth=3.2, solid_capstyle="round", zorder=3)
    ax.fill_between(timestamps, closes, previous_close, color=fill_color, alpha=0.82, zorder=2)
    ax.axhline(previous_close, color="#f4a261", linewidth=1.5, linestyle=(0, (5, 4)), zorder=1)
    ax.scatter(timestamps[-1], closes[-1], s=42, color=line_color, zorder=5)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.grid(axis="y", color="#d7dee8", linewidth=0.9, alpha=0.95)
    ax.grid(axis="x", color="#edf1f6", linewidth=0.6, alpha=0.75)
    ax.tick_params(axis="x", labelsize=10, colors="#5c6773", pad=8)
    ax.tick_params(axis="y", labelsize=10, colors="#5c6773")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

    step = max(1, len(timestamps) // 6)
    tick_positions = timestamps[::step]
    if tick_positions[-1] != timestamps[-1]:
        tick_positions.append(timestamps[-1])
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([tick.strftime("%H:%M") for tick in tick_positions])

    pct_axis = ax.twinx()
    pct_axis.set_ylim(ax.get_ylim())
    pct_axis.spines["left"].set_visible(False)
    pct_axis.spines["right"].set_position(("axes", 1.08))
    pct_axis.spines["right"].set_visible(False)
    pct_axis.tick_params(axis="y", labelsize=9, colors="#8a96a3")
    pct_axis.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _: f"{((value - previous_close) / previous_close) * 100:+.2f}%")
    )

    title = "TAIEX Session Trend"
    subtitle = (
        f"{latest_price:,.0f}  "
        f"{change_amount:+.2f} ({change_percent:+.2f}%)  "
        f"vs Prev Close {previous_close:,.0f}"
    )
    fig.text(0.07, 0.91, title, fontsize=22, fontweight="bold", color="#243447")
    fig.text(0.07, 0.872, subtitle, fontsize=11.5, color="#4f5d6b")

    ax.annotate(
        f"Now {latest_price:,.0f}",
        xy=(timestamps[-1], closes[-1]),
        xytext=(-12, 18),
        textcoords="offset points",
        ha="right",
        fontsize=10.2,
        color="#243447",
        bbox={"boxstyle": "round,pad=0.35", "fc": "#ffffff", "ec": "#d7dee8"},
    )
    ax.annotate(
        f"Prev Close {previous_close:,.0f}",
        xy=(timestamps[-1], previous_close),
        xytext=(-10, -22),
        textcoords="offset points",
        ha="right",
        fontsize=9,
        color="#8a5a14",
    )

    high_idx = closes.index(session_high)
    low_idx = closes.index(session_low)
    ax.annotate(
        f"H {session_high:,.0f}",
        xy=(timestamps[high_idx], session_high),
        xytext=(0, -18),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#243447",
    )
    ax.annotate(
        f"L {session_low:,.0f}",
        xy=(timestamps[low_idx], session_low),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#243447",
    )

    summary_boxes = [
        ("Open", f"{session_open:,.0f}"),
        ("High", f"{session_high:,.0f}"),
        ("Low", f"{session_low:,.0f}"),
        ("Prev Close", f"{previous_close:,.0f}"),
    ]
    start_x = 0.07
    for label, value in summary_boxes:
        fig.text(
            start_x,
            0.82,
            label,
            fontsize=8.8,
            color="#7a8694",
            bbox={"boxstyle": "round,pad=0.28", "fc": "#eef3f8", "ec": "#eef3f8"},
        )
        fig.text(start_x, 0.792, value, fontsize=10.5, color="#243447", fontweight="bold")
        start_x += 0.13

    status_text = "Live Session" if timestamps[-1].date() == datetime.datetime.now(timestamps[-1].tz).date() else "Previous Session"
    status_color = "#d64045" if status_text == "Live Session" else "#607086"
    fig.text(
        0.84,
        0.905,
        status_text,
        fontsize=10,
        color=status_color,
        bbox={"boxstyle": "round,pad=0.35", "fc": "#ffffff", "ec": "#d7dee8"},
    )

    fig.text(
        0.015,
        0.02,
        f"Source: Yahoo Finance ^TWII | Updated {timestamps[-1].strftime('%Y-%m-%d %H:%M')}",
        fontsize=8.5,
        color="#7a8694",
    )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file.close()
    fig.savefig(temp_file.name, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return temp_file.name

def build_stock_chart(snapshot):
    session = snapshot["session"]
    closes = [float(value) for value in session.tolist()]
    timestamps = list(session.index)
    previous_close = snapshot["previous_close"]
    latest_price = snapshot["current_price"]
    change_amount = snapshot["change_amount"]
    change_percent = snapshot["change_percent"]
    line_color = "#d64045" if change_amount < 0 else "#138a5c"
    fill_color = "#f6d9dc" if change_amount < 0 else "#d7f0e4"

    fig = plt.figure(figsize=(12.6, 7.2), dpi=160, facecolor="#f3f6fb")
    ax = fig.add_axes([0.07, 0.14, 0.88, 0.68])
    ax.set_facecolor("#ffffff")

    ax.plot(timestamps, closes, color=line_color, linewidth=3.2, solid_capstyle="round", zorder=3)
    ax.fill_between(timestamps, closes, previous_close, color=fill_color, alpha=0.82, zorder=2)
    ax.axhline(previous_close, color="#f4a261", linewidth=1.5, linestyle=(0, (5, 4)), zorder=1)
    ax.scatter(timestamps[-1], closes[-1], s=42, color=line_color, zorder=5)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.grid(axis="y", color="#d7dee8", linewidth=0.9, alpha=0.95)
    ax.grid(axis="x", color="#edf1f6", linewidth=0.6, alpha=0.75)
    ax.tick_params(axis="x", labelsize=10, colors="#5c6773", pad=8)
    ax.tick_params(axis="y", labelsize=10, colors="#5c6773")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.2f}"))
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

    step = max(1, len(timestamps) // 6)
    tick_positions = timestamps[::step]
    if tick_positions[-1] != timestamps[-1]:
        tick_positions.append(timestamps[-1])
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([tick.strftime("%H:%M") for tick in tick_positions])

    pct_axis = ax.twinx()
    pct_axis.set_ylim(ax.get_ylim())
    pct_axis.spines["left"].set_visible(False)
    pct_axis.spines["right"].set_position(("axes", 1.08))
    pct_axis.spines["right"].set_visible(False)
    pct_axis.tick_params(axis="y", labelsize=9, colors="#8a96a3")
    pct_axis.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _: f"{((value - previous_close) / previous_close) * 100:+.2f}%")
    )

    fig.text(0.07, 0.91, f"{snapshot['code']}  {snapshot['name']}", fontsize=22, fontweight="bold", color="#243447")
    fig.text(
        0.07,
        0.872,
        f"{latest_price:,.2f}  {change_amount:+.2f} ({change_percent:+.2f}%)  vs Prev Close {previous_close:,.2f}",
        fontsize=11.5,
        color="#4f5d6b",
    )

    ax.annotate(
        f"Now {latest_price:,.2f}",
        xy=(timestamps[-1], closes[-1]),
        xytext=(-12, 18),
        textcoords="offset points",
        ha="right",
        fontsize=10.2,
        color="#243447",
        bbox={"boxstyle": "round,pad=0.35", "fc": "#ffffff", "ec": "#d7dee8"},
    )
    ax.annotate(
        f"Prev Close {previous_close:,.2f}",
        xy=(timestamps[-1], previous_close),
        xytext=(-10, -22),
        textcoords="offset points",
        ha="right",
        fontsize=9,
        color="#8a5a14",
    )

    high_price = snapshot["high_price"]
    low_price = snapshot["low_price"]
    ax.annotate(
        f"H {high_price:,.2f}",
        xy=(timestamps[closes.index(high_price)], high_price),
        xytext=(0, -18),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#243447",
    )
    ax.annotate(
        f"L {low_price:,.2f}",
        xy=(timestamps[closes.index(low_price)], low_price),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#243447",
    )

    summary_boxes = [
        ("Open", f"{snapshot['open_price']:,.2f}"),
        ("High", f"{high_price:,.2f}"),
        ("Low", f"{low_price:,.2f}"),
        ("Prev Close", f"{previous_close:,.2f}"),
    ]
    start_x = 0.07
    for label, value in summary_boxes:
        fig.text(
            start_x,
            0.82,
            label,
            fontsize=8.8,
            color="#7a8694",
            bbox={"boxstyle": "round,pad=0.28", "fc": "#eef3f8", "ec": "#eef3f8"},
        )
        fig.text(start_x, 0.792, value, fontsize=10.5, color="#243447", fontweight="bold")
        start_x += 0.13

    today = datetime.datetime.now(timestamps[-1].tz).date()
    status_text = "Live Session" if timestamps[-1].date() == today else "Previous Session"
    status_color = "#d64045" if status_text == "Live Session" else "#607086"
    fig.text(
        0.82,
        0.905,
        status_text,
        fontsize=10,
        color=status_color,
        bbox={"boxstyle": "round,pad=0.35", "fc": "#ffffff", "ec": "#d7dee8"},
    )

    fig.text(
        0.015,
        0.02,
        f"Source: Yahoo Finance {snapshot['symbol']} | Updated {timestamps[-1].strftime('%Y-%m-%d %H:%M')}",
        fontsize=8.5,
        color="#7a8694",
    )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file.close()
    fig.savefig(temp_file.name, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return temp_file.name


def build_taifex_night_chart(snapshot):
    open_price = snapshot["open_price"]
    high_price = snapshot["high_price"]
    low_price = snapshot["low_price"]
    last_price = snapshot["last_price"]
    change_amount = snapshot["change_amount"] or 0.0
    change_percent = snapshot["change_percent"] or 0.0
    color = "#d64045" if change_amount < 0 else "#138a5c"
    fill_color = "#f6d9dc" if change_amount < 0 else "#d7f0e4"

    fig = plt.figure(figsize=(10.8, 6.6), dpi=160, facecolor="#0f1720")
    ax = fig.add_axes([0.08, 0.16, 0.48, 0.68])
    ax.set_facecolor("#15202b")

    padding = max(60, (high_price - low_price) * 0.2)
    ax.set_ylim(low_price - padding, high_price + padding)
    ax.set_xlim(-0.8, 0.8)
    ax.axhline(last_price, color=color, alpha=0.18, linewidth=12, zorder=1)
    ax.vlines(0, low_price, high_price, color="#cfd8e3", linewidth=5, zorder=2)
    candle_bottom = min(open_price, last_price)
    candle_height = max(abs(last_price - open_price), 1)
    ax.bar(0, candle_height, bottom=candle_bottom, width=0.42, color=fill_color, edgecolor=color, linewidth=2.5, zorder=3)
    ax.scatter([0], [last_price], color=color, s=70, zorder=4)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=10, colors="#d4dee8")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.grid(axis="y", color="#324150", linewidth=0.8, alpha=0.65)

    ax.annotate(f"H {high_price:,.0f}", xy=(0, high_price), xytext=(10, -4), textcoords="offset points", color="#d4dee8", fontsize=9)
    ax.annotate(f"L {low_price:,.0f}", xy=(0, low_price), xytext=(10, -4), textcoords="offset points", color="#d4dee8", fontsize=9)
    ax.annotate(f"Last {last_price:,.0f}", xy=(0, last_price), xytext=(10, 6), textcoords="offset points", color="#ffffff", fontsize=10, fontweight="bold")

    fig.text(0.08, 0.91, "TX Night Session", fontsize=22, fontweight="bold", color="#f8fafc")
    fig.text(
        0.08,
        0.868,
        f"{snapshot['contract']}  {last_price:,.0f}  {change_amount:+.0f} ({change_percent:+.2f}%)",
        fontsize=12,
        color="#d7e0ea",
    )
    session_label = "15:00-05:00 Night Session"
    fig.text(0.08, 0.835, session_label, fontsize=9.5, color="#94a3b8")

    info_lines = [
        ("Open", f"{open_price:,.0f}"),
        ("High", f"{high_price:,.0f}"),
        ("Low", f"{low_price:,.0f}"),
        ("Last", f"{last_price:,.0f}"),
        ("Prev Close", f"{snapshot['previous_close']:,.0f}" if snapshot.get("previous_close") is not None else "-"),
        ("Avg", f"{snapshot['average_price']:,.2f}" if snapshot.get("average_price") is not None else "-"),
        ("Volume", f"{int(snapshot['volume']):,}" if snapshot["volume"] is not None else "-"),
        ("Best Bid", f"{snapshot['best_bid']:,.0f}" if snapshot["best_bid"] is not None else "-"),
        ("Best Ask", f"{snapshot['best_ask']:,.0f}" if snapshot["best_ask"] is not None else "-"),
    ]
    y = 0.74
    for label, value in info_lines:
        fig.text(0.64, y, label, fontsize=10, color="#8ea1b5")
        fig.text(0.64, y - 0.045, value, fontsize=16, fontweight="bold", color="#f8fafc")
        y -= 0.105

    updated_at = snapshot.get("updated_at")
    updated_text = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else snapshot["report_date"]
    source_url = snapshot.get("source_url", "").lower()
    if "yahoo" in source_url:
        source_label = "Yahoo WTX&"
    elif "wantgoo" in source_url:
        source_label = "WantGoo WTXP&"
    else:
        source_label = "TAIFEX TX night market"
    fig.text(0.08, 0.04, f"Source: {source_label} | Updated {updated_text}", fontsize=8.8, color="#94a3b8")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file.close()
    fig.savefig(temp_file.name, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return temp_file.name


def build_taifex_night_candles_chart(snapshot, candles):
    change_amount = snapshot["change_amount"] or 0.0
    change_percent = snapshot["change_percent"] or 0.0
    fig = plt.figure(figsize=(12.8, 7.0), dpi=160, facecolor="#0f1720")
    ax = fig.add_axes([0.07, 0.18, 0.88, 0.64])
    ax.set_facecolor("#15202b")

    highs = [candle["high"] for candle in candles]
    lows = [candle["low"] for candle in candles]
    min_price = min(lows)
    max_price = max(highs)
    padding = max(35, (max_price - min_price) * 0.2)
    ax.set_ylim(min_price - padding, max_price + padding)
    ax.grid(axis="y", color="#324150", linewidth=0.8, alpha=0.65)
    ax.grid(axis="x", color="#22303d", linewidth=0.6, alpha=0.45)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.tick_params(axis="x", labelsize=9, colors="#d4dee8", pad=8)
    ax.tick_params(axis="y", labelsize=10, colors="#d4dee8")
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))

    x_values = list(range(len(candles)))
    for idx, candle in enumerate(candles):
        up = candle["close"] >= candle["open"]
        edge_color = "#22c55e" if up else "#ef4444"
        fill_color = "#d7f0e4" if up else "#f6d9dc"
        ax.vlines(idx, candle["low"], candle["high"], color=edge_color, linewidth=1.6, zorder=2)
        body_bottom = min(candle["open"], candle["close"])
        body_height = max(abs(candle["close"] - candle["open"]), 1)
        ax.bar(idx, body_height, bottom=body_bottom, width=0.62, color=fill_color, edgecolor=edge_color, linewidth=1.5, zorder=3)

    step = max(1, len(candles) // 8)
    tick_positions = x_values[::step]
    if tick_positions[-1] != x_values[-1]:
        tick_positions.append(x_values[-1])
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([candles[idx]["time"].strftime("%H:%M") for idx in tick_positions])

    fig.text(0.07, 0.91, "TX Night Session", fontsize=22, fontweight="bold", color="#f8fafc")
    fig.text(
        0.07,
        0.872,
        f"{snapshot['contract']}  {snapshot['last_price']:,.0f}  {change_amount:+.0f} ({change_percent:+.2f}%)",
        fontsize=12,
        color="#d7e0ea",
    )
    fig.text(0.07, 0.838, f"5-min candles from sampled TAIFEX quotes | bars {len(candles)}", fontsize=9.5, color="#94a3b8")

    info_lines = [
        ("Open", f"{snapshot['open_price']:,.0f}"),
        ("High", f"{snapshot['high_price']:,.0f}"),
        ("Low", f"{snapshot['low_price']:,.0f}"),
        ("Last", f"{snapshot['last_price']:,.0f}"),
        ("Prev Close", f"{snapshot['previous_close']:,.0f}" if snapshot.get("previous_close") is not None else "-"),
        ("Volume", f"{int(snapshot['volume']):,}" if snapshot["volume"] is not None else "-"),
    ]
    y = 0.74
    for label, value in info_lines:
        fig.text(0.80, y, label, fontsize=10, color="#8ea1b5")
        fig.text(0.80, y - 0.042, value, fontsize=15, fontweight="bold", color="#f8fafc")
        y -= 0.10

    updated_at = snapshot.get("updated_at")
    updated_text = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else snapshot["report_date"]
    source_url = snapshot.get("source_url", "").lower()
    if "yahoo" in source_url:
        source_label = "Yahoo WTX&"
    elif "wantgoo" in source_url:
        source_label = "WantGoo WTXP&"
    else:
        source_label = "TAIFEX TX night market"
    fig.text(0.07, 0.04, f"Source: {source_label} | Updated {updated_text}", fontsize=8.8, color="#94a3b8")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file.close()
    fig.savefig(temp_file.name, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return temp_file.name
