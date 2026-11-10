import datetime
from io import BytesIO

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter


def figure_png(figure):
    FigureCanvasAgg(figure)
    with BytesIO() as buffer:
        figure.savefig(buffer, format="png", bbox_inches="tight", facecolor=figure.get_facecolor())
        return buffer.getvalue()


def build_taiex_chart(session, previous_close, *, symbol, title):
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

    fig = Figure(figsize=(12.6, 7.2), dpi=160, facecolor="#f3f6fb")
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
        f"Source: Yahoo Finance {symbol} | Updated {timestamps[-1].strftime('%Y-%m-%d %H:%M')}",
        fontsize=8.5,
        color="#7a8694",
    )

    return figure_png(fig)

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

    fig = Figure(figsize=(12.6, 7.2), dpi=160, facecolor="#f3f6fb")
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

    return figure_png(fig)


def build_history_chart(snapshot):
    series = snapshot["series"]
    comparison = len(series) > 1
    title = "Adjusted return comparison" if comparison else f"{next(iter(series))} adjusted close"
    fig = Figure(figsize=(11.5, 6.4), dpi=150, facecolor="#f3f6fb", layout="constrained")
    ax = fig.subplots()
    palette = ("#2458a6", "#ce5629", "#168765", "#8842a1", "#a07106")
    for color, (code, values) in zip(palette, series.items()):
        ax.plot(values.index, values, color=color, label=code, linewidth=1.8)
    if comparison:
        ax.axhline(0, color="#738397", linewidth=0.9, linestyle="--")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:+.0f}%"))
        ax.set_ylabel("Return from first common date")
        ax.legend(loc="best", frameon=False)
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.2f}"))
        ax.set_ylabel("Adjusted close (local currency)")
    locator = AutoDateLocator(minticks=4, maxticks=9)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    ax.grid(axis="y", alpha=0.24)
    ax.set_title(f"{title}  |  {snapshot['period']}  |  Yahoo Finance", loc="left", fontweight="bold")
    return figure_png(fig)


def build_night_chart(snapshot, bars):
    last = snapshot["last_price"]
    previous = snapshot.get("previous_close")
    change = snapshot["change_amount"]
    percent = snapshot["change_percent"]
    color = "#18a95d" if change is not None and change < 0 else "#e35358" if change else "#94a3b8"
    muted = "#94a3b8"
    background = "#0b0f14"
    fig = Figure(figsize=(11.5, 7.9), dpi=160, facecolor=background)
    ax = fig.add_axes([0.03, 0.18, 0.88, 0.60], facecolor=background)
    volumes = [(bar["time"], bar["volume"]) for bar in bars if bar["volume"] is not None]
    if volumes:
        volume_ax = fig.add_axes([0.03, 0.075, 0.88, 0.095], sharex=ax, facecolor=background)
        volume_ax.bar(
            [time for time, _ in volumes], [value for _, value in volumes],
            width=4 / (24 * 60), color=color, alpha=0.42,
        )
        volume_ax.set_yticks([])
        volume_ax.set_ylabel("5m vol", color=muted, rotation=0, labelpad=14, fontsize=7)
        volume_ax.yaxis.set_label_position("right")
        for spine in volume_ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="x", labelbottom=False)
        time_ax = volume_ax
    else:
        time_ax = ax

    updated_at = snapshot.get("updated_at")
    times = [bar["time"] for bar in bars]
    prices = [bar["close"] for bar in bars]
    if updated_at is not None and (not times or updated_at > times[-1]):
        times.append(updated_at)
        prices.append(last)
    elif times:
        prices[-1] = last

    if times:
        ax.plot(times, prices, color=color, linewidth=2.8, solid_capstyle="round", zorder=3)
        baseline = snapshot["open_price"] if snapshot["open_price"] is not None else last
        ax.fill_between(times, prices, baseline, color=color, alpha=0.09)
        ax.scatter(times[-1], last, color=color, edgecolors="white", s=34, zorder=4)
        ax.annotate(f"{last:,.0f}", (times[-1], last), xytext=(7, 0), textcoords="offset points",
                    va="center", color="white", fontsize=10, fontweight="bold",
                    bbox={"boxstyle": "round,pad=0.25", "fc": color, "ec": "none"})
        step = max(1, (len(times) + 7) // 8)
        ticks = times[::step]
        time_ax.set_xticks(ticks, [time.strftime("%H:%M") for time in ticks])
        ax.margins(x=0.06)
    else:
        time_ax.set_xticks([])

    if previous is not None:
        ax.axhline(previous, color="#489dce", linestyle="--", linewidth=1.2)
        ax.annotate("Prev Close", (0.04, previous), xycoords=("axes fraction", "data"),
                    xytext=(0, 3), textcoords="offset points", color="#489dce", fontsize=9)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color="#26303a", alpha=0.32)
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.tick_params(axis="y", colors=muted, length=0, labelsize=9)
    time_ax.tick_params(axis="x", colors=muted, length=0, labelsize=9)

    fig.text(0.03, 0.94, "TX NIGHT SESSION", fontsize=23, fontweight="bold", color="white")
    fig.text(0.03, 0.875, f"{last:,.0f}", fontsize=34, fontweight="bold", color="white")
    change_text = f"{change:+,.0f} ({percent:+.2f}%)" if change is not None and percent is not None else "Change unavailable"
    fig.text(0.25, 0.883, change_text, fontsize=19, fontweight="bold", color=color)
    for i, (label, key) in enumerate((("OPEN", "open_price"), ("HIGH", "high_price"), ("LOW", "low_price"), ("VOLUME", "volume"))):
        x = 0.03 + i * 0.17
        value = snapshot.get(key)
        fig.text(x, 0.823, label, fontsize=8, fontweight="bold", color=muted)
        fig.text(x, 0.788, f"{value:,.0f}" if value is not None else "-", fontsize=14,
                 fontweight="bold", color="white")

    source = "Yahoo WTX&" if snapshot.get("source") == "yahoo" else "TAIFEX TX"
    coverage = "5-min history" if snapshot.get("history") else "5-min local samples" if bars else "Quote only"
    updated = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else snapshot["report_date"]
    fig.text(0.03, 0.024, f"{source} | {coverage}", fontsize=8, color=muted)
    fig.text(0.96, 0.024, f"Updated {updated}", ha="right", fontsize=8, color=muted)
    return figure_png(fig)
