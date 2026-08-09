from dataclasses import dataclass
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "url-resolver" / "config.toml"


@dataclass
class AppConfig:
    aria2_host: str = "ws://heritage.bun-bull.ts.net:6800"
    aria2_secret: str = ""


def load_config() -> AppConfig:
    if not DEFAULT_CONFIG_PATH.exists():
        return AppConfig()
    with open(DEFAULT_CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)
    aria2_data = data.get("aria2", {})
    return AppConfig(
        aria2_host=aria2_data.get("host", "ws://heritage.bun-bull.ts.net:6800"),
        aria2_secret=aria2_data.get("secret", ""),
    )
