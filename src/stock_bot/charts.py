from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter


BACKGROUND = "#0b0f14"
MUTED = "#94a3b8"
FOREGROUND = "#f8fafc"
REFERENCE = "#489dce"
PALETTE = ("#62a5ed", "#f19966", "#54c7a3", "#c291ec", "#e6c46a")
TAIPEI_TIME = ZoneInfo("Asia/Taipei")


def figure_png(figure):
    FigureCanvasAgg(figure)
    with BytesIO() as buffer:
        figure.savefig(buffer, format="png", facecolor=figure.get_facecolor())
        return buffer.getvalue()


def price_text(value, decimals):
    return f"{value:,.{decimals}f}" if value is not None else "-"


def trend_color(change):
    if change is None or change == 0:
        return MUTED
    return "#18a95d" if change < 0 else "#e35358"


def style_axes(ax):
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", colors=MUTED, length=0, labelsize=9)


def chart_frame(title, *, has_volume=False):
    fig = Figure(figsize=(11.5, 7.9), dpi=160, facecolor=BACKGROUND)
    bottom = 0.18 if has_volume else 0.10
    ax = fig.add_axes([0.04, bottom, 0.86, 0.76 - bottom], facecolor=BACKGROUND)
    style_axes(ax)
    ax.yaxis.tick_right()
    ax.grid(axis="y", color="#26303a", alpha=0.4)
    ax.set_axisbelow(True)
    fig.text(0.04, 0.94, title, fontsize=23 if len(title) <= 45 else 17,
             fontweight="bold", color=FOREGROUND)
    return fig, ax


def headline(fig, price, change, percent, decimals):
    fig.text(0.04, 0.875, price_text(price, decimals), fontsize=32,
             fontweight="bold", color=FOREGROUND)
    if change is not None and percent is not None:
        fig.text(0.33, 0.883, f"{change:+,.{decimals}f} ({percent:+.2f}%)",
                 fontsize=18, fontweight="bold", color=trend_color(change))


def metrics(fig, items):
    for i, (label, value, color) in enumerate(items):
        x = 0.04 + i * 0.18
        fig.text(x, 0.823, label, fontsize=9, fontweight="bold", color=MUTED)
        fig.text(x, 0.787, value, fontsize=14, fontweight="bold", color=color)


def price_line(ax, times, prices, *, previous, baseline, color, decimals):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: price_text(value, decimals)))
    if not times:
        return
    ax.plot(times, prices, color=color, linewidth=2.6, solid_capstyle="round", zorder=3)
    if baseline is not None:
        ax.fill_between(times, prices, baseline, color=color, alpha=0.09)
    if previous is not None:
        ax.axhline(previous, color=REFERENCE, linestyle="--", linewidth=1.2)
        ax.annotate("Prev Close", (0.04, previous), xycoords=("axes fraction", "data"),
                    xytext=(0, 3), textcoords="offset points", color=REFERENCE, fontsize=9)
    ax.scatter(times[-1], prices[-1], color=color, edgecolors="white", s=34, zorder=4)
    ax.annotate(price_text(prices[-1], decimals), (times[-1], prices[-1]),
                xytext=(-7, 10), textcoords="offset points", ha="right", va="bottom",
                color=BACKGROUND, fontsize=10, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.25", "fc": color, "ec": "none"})
    ax.margins(x=0.05, y=0.10)


def intraday_ticks(fig, ax, times):
    by_minute = {time.strftime("%H:%M"): time for time in times}
    labels = list(by_minute)
    count = min(8, len(labels))
    indices = [round(i * (len(labels) - 1) / (count - 1)) for i in range(count)] if count > 1 else range(count)
    selected = [labels[i] for i in indices]
    ax.set_xticks([by_minute[label] for label in selected], selected)
    if times:
        latest = times[-1]
        zone = str(latest.tzinfo)
        if zone in {"America/New_York", "US/Eastern"}:
            label = "ET"
        elif zone == "Asia/Taipei":
            label = "Taipei time"
        else:
            label = latest.tzname()
        if label:
            fig.text(0.94, 0.785, f"Time axis: {label}", ha="right", fontsize=8, color=MUTED)


def history_ticks(ax):
    locator = AutoDateLocator(minticks=4, maxticks=9)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))


def updated_footer(fig, timestamp):
    label = timestamp
    if not isinstance(timestamp, str):
        if timestamp.utcoffset() is not None:
            label = timestamp.astimezone(TAIPEI_TIME).strftime("%Y-%m-%d %H:%M Taipei")
        else:
            label = timestamp.strftime("%Y-%m-%d %H:%M")
    fig.text(0.94, 0.024, f"Updated {label}", ha="right", fontsize=8, color=MUTED)


def build_session_chart(session, previous, title, decimals):
    times = list(session.index)
    prices = [float(value) for value in session]
    if len(prices) < 2:
        raise ValueError("盤中資料點不足，無法生成圖表")

    last = prices[-1]
    change = last - previous
    percent = change / previous * 100 if previous else None
    fig, ax = chart_frame(title)
    headline(fig, last, change, percent, decimals)
    latest = times[-1]
    session_date = latest.date()
    current_date = datetime.now(latest.tzinfo).date()
    session_label = "Previous session" if session_date < current_date else "Session date"
    fig.text(0.94, 0.878, f"{session_label}: {session_date:%Y-%m-%d}",
             ha="right", fontsize=10, color=MUTED)
    metrics(fig, [(label, price_text(value, decimals), FOREGROUND) for label, value in (
        ("OPEN", prices[0]), ("HIGH", max(prices)), ("LOW", min(prices)), ("PREV CLOSE", previous),
    )])
    price_line(ax, times, prices, previous=previous, baseline=previous,
               color=trend_color(change), decimals=decimals)
    intraday_ticks(fig, ax, times)
    updated_footer(fig, latest)
    return figure_png(fig)


def build_taiex_chart(session, previous_close, *, title):
    return build_session_chart(session, previous_close, title, 0)


def build_stock_chart(snapshot):
    title = f"{snapshot['code']}  {snapshot['name']}"
    return build_session_chart(snapshot["session"], snapshot["previous_close"], title, 2)


def build_history_chart(snapshot):
    series = snapshot["series"]
    period = snapshot["period"]
    code, first = next(iter(series.items()))
    dates = f"{first.index[0]:%Y-%m-%d} to {first.index[-1]:%Y-%m-%d}"
    if len(series) == 1:
        fig, ax = chart_frame(f"{code} ADJUSTED CLOSE")
        change = first.iloc[-1] - first.iloc[0]
        headline(fig, first.iloc[-1], change, change / first.iloc[0] * 100, 2)
        metrics(fig, [("PERIOD", period, FOREGROUND), ("DATE RANGE", dates, FOREGROUND)])
        price_line(ax, list(first.index), first.tolist(), previous=None, baseline=first.iloc[0],
                   color=trend_color(change), decimals=2)
    else:
        fig, ax = chart_frame("ADJUSTED RETURN COMPARISON")
        fig.text(0.04, 0.875, f"{period}  |  {dates}", fontsize=14, color=MUTED)
        items = []
        for color, (code, values) in zip(PALETTE, series.items()):
            ax.plot(values.index, values, color=color, linewidth=2.0)
            items.append((code, f"{values.iloc[-1]:+.2f}%", color))
        metrics(fig, items)
        ax.axhline(0, color=REFERENCE, linestyle="--", linewidth=1.1)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:+.0f}%"))
        ax.margins(x=0.04, y=0.10)
    history_ticks(ax)
    return figure_png(fig)


def build_night_chart(snapshot, bars):
    last = snapshot["last_price"]
    previous = snapshot.get("previous_close")
    change = snapshot["change_amount"]
    percent = snapshot["change_percent"]
    color = trend_color(change)
    volumes = [(bar["time"], bar["volume"]) for bar in bars if bar["volume"] is not None]
    fig, ax = chart_frame("TX NIGHT SESSION", has_volume=bool(volumes))

    time_ax = ax
    if volumes:
        time_ax = fig.add_axes([0.04, 0.075, 0.86, 0.095], sharex=ax, facecolor=BACKGROUND)
        style_axes(time_ax)
        time_ax.bar([time for time, _ in volumes], [value for _, value in volumes],
                    width=4 / (24 * 60), color=color, alpha=0.42)
        time_ax.set_yticks([])
        time_ax.set_ylabel("5m vol", color=MUTED, rotation=0, labelpad=14, fontsize=7)
        time_ax.yaxis.set_label_position("right")
        ax.tick_params(axis="x", labelbottom=False)

    updated_at = snapshot.get("updated_at")
    times = [bar["time"] for bar in bars]
    prices = [bar["close"] for bar in bars]
    if updated_at is not None and (not times or updated_at > times[-1]):
        times.append(updated_at)
        prices.append(last)
    elif times:
        prices[-1] = last

    price_line(ax, times, prices, previous=previous, baseline=snapshot.get("open_price"),
               color=color, decimals=0)
    intraday_ticks(fig, time_ax, times)
    headline(fig, last, change, percent, 0)
    metrics(fig, [(label, price_text(snapshot.get(key), 0), FOREGROUND)
                  for label, key in (("OPEN", "open_price"), ("HIGH", "high_price"),
                                     ("LOW", "low_price"), ("VOLUME", "volume"))])
    updated_footer(fig, updated_at or snapshot["report_date"])
    return figure_png(fig)
