import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class BotConfig:
    token: str = field(repr=False)
    nickname: str
    queue_size: int
    request_timeout_seconds: float
    query_timeout_seconds: float
    sample_file: Path
    yahoo_night_url: str
    taifex_night_url: str
    night_aliases: frozenset[str]


def read_toml(path: Path):
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except tomllib.TOMLDecodeError:
        raise ValueError("設定檔不是有效的 TOML") from None


def validate_sections(config, sections):
    if config.keys() - sections.keys():
        raise ValueError("設定檔含有未知的區段")
    for name, keys in sections.items():
        section = config.get(name, {})
        if not isinstance(section, dict) or section.keys() - keys:
            raise ValueError(f"設定區段 {name} 含有無效欄位")


def required_url(section, key, prefix, *, base=False):
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix}.{key} 必須填寫")
    value = value.strip()
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.fragment
        if base and parsed.query:
            valid = False
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"{prefix}.{key} 必須是有效的 HTTP 或 HTTPS 網址")
    return value.rstrip("/") if base else value


def load_config(path: Path) -> BotConfig:
    config = read_toml(path)
    config.pop("report", None)
    validate_sections(config, {
        "discord": {"token", "nickname"},
        "quotes": {"queue_size", "request_timeout_seconds", "query_timeout_seconds"},
        "night": {"sample_file", "yahoo_url", "taifex_url", "aliases"},
    })

    discord = config.get("discord", {})
    quotes = config.get("quotes", {})
    night = config.get("night", {})
    token = discord.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("discord.token 必須填寫")
    nickname = discord.get("nickname", "股市小幫手")
    if not isinstance(nickname, str) or not nickname.strip():
        raise ValueError("discord.nickname 必須是非空文字")
    queue_size = quotes.get("queue_size", 4)
    if type(queue_size) is not int or queue_size <= 0:
        raise ValueError("quotes.queue_size 必須是正整數")

    def timeout(key, default):
        value = quotes.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"quotes.{key} 必須是有限的正數")
        return value

    sample_file = night.get("sample_file", "data/night-samples.jsonl")
    if not isinstance(sample_file, str) or not sample_file.strip() or "\0" in sample_file:
        raise ValueError("night.sample_file 必須是有效的檔案路徑")
    sample_path = path.resolve().parent / sample_file
    if sample_path.is_dir():
        raise ValueError("night.sample_file 必須指向檔案")

    aliases = night.get("aliases")
    if not isinstance(aliases, list) or not aliases or any(
        not isinstance(alias, str) or not alias.strip() for alias in aliases
    ):
        raise ValueError("night.aliases 必須是非空文字清單")

    return BotConfig(
        token=token.strip(),
        nickname=nickname.strip(),
        queue_size=queue_size,
        request_timeout_seconds=timeout("request_timeout_seconds", 20),
        query_timeout_seconds=timeout("query_timeout_seconds", 30),
        sample_file=sample_path,
        yahoo_night_url=required_url(night, "yahoo_url", "night"),
        taifex_night_url=required_url(night, "taifex_url", "night"),
        night_aliases=frozenset(alias.strip().lower() for alias in aliases),
    )


@dataclass(frozen=True)
class ReportSources:
    quote_url: str
    sentiment_url: str
    sentiment_referer: str
    calendar_url: str


@dataclass(frozen=True)
class ReportConfig:
    webhook_url: str = field(repr=False)
    mention_user_id: str
    index_symbol: str
    index_label: str
    chart_title: str
    sources: ReportSources


def load_report_config(path: Path) -> ReportConfig:
    config = read_toml(path).get("report")
    if not isinstance(config, dict):
        raise ValueError("設定檔缺少 [report] 區段")
    if "watchlist" in config or "quotes" in config:
        raise ValueError("請將舊快報股票清單移到 scripts/tw_market_report.py 的 WATCHLIST，再移除設定檔中的清單")
    validate_sections(config, {
        "discord": {"webhook_url", "mention_user_id"},
        "index": {"symbol", "label", "chart_title"},
        "sources": {"quote_url", "sentiment_url", "sentiment_referer", "calendar_url"},
    })

    def required_text(section, key, prefix):
        value = section.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{prefix}.{key} 必須填寫")
        return value.strip()

    discord = config.get("discord", {})
    webhook = required_text(discord, "webhook_url", "discord")
    if not re.fullmatch(r"https://(?:canary\.|ptb\.)?discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+", webhook):
        raise ValueError("discord.webhook_url 必須是有效的 Discord webhook 網址")
    mention = discord.get("mention_user_id", "")
    if not isinstance(mention, str) or (mention and not re.fullmatch(r"[0-9]+", mention)):
        raise ValueError("discord.mention_user_id 必須是數字字串或空字串")

    index = config.get("index", {})
    index_symbol = required_text(index, "symbol", "index")
    index_label = required_text(index, "label", "index")
    chart_title = required_text(index, "chart_title", "index")

    sources = config.get("sources", {})

    return ReportConfig(
        webhook_url=webhook,
        mention_user_id=mention,
        index_symbol=index_symbol,
        index_label=index_label,
        chart_title=chart_title,
        sources=ReportSources(
            quote_url=required_url(sources, "quote_url", "sources"),
            sentiment_url=required_url(sources, "sentiment_url", "sources"),
            sentiment_referer=required_url(sources, "sentiment_referer", "sources"),
            calendar_url=required_url(sources, "calendar_url", "sources", base=True),
        ),
    )
