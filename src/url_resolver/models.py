from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DownloadMetadata:
    direct_url: str
    referer: str
    user_agent: str
    filename: Optional[str]
    source_page: str
    tag: Optional[str] = None
    models: list[str] = field(default_factory=list)
