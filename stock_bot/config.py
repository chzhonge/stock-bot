import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BotConfig:
    token: str = field(repr=False)
    nickname: str
    queue_size: int
    request_timeout_seconds: float
    query_timeout_seconds: float
    sample_file: Path


def load_config(path: Path) -> BotConfig:
    try:
        with path.open("rb") as config_file:
            config = tomllib.load(config_file)
    except tomllib.TOMLDecodeError:
        raise ValueError("設定檔不是有效的 TOML") from None

    sections = {
        "discord": {"token", "nickname"},
        "quotes": {"queue_size", "request_timeout_seconds", "query_timeout_seconds"},
        "night": {"sample_file"},
    }
    if config.keys() - sections.keys():
        raise ValueError("設定檔含有未知的區段")
    for name, keys in sections.items():
        section = config.get(name, {})
        if not isinstance(section, dict) or section.keys() - keys:
            raise ValueError(f"設定區段 {name} 含有無效欄位")

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

    return BotConfig(
        token=token.strip(),
        nickname=nickname.strip(),
        queue_size=queue_size,
        request_timeout_seconds=timeout("request_timeout_seconds", 20),
        query_timeout_seconds=timeout("query_timeout_seconds", 30),
        sample_file=sample_path,
    )
