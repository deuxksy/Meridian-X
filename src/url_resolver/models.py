from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadMetadata:
    direct_url: str
    referer: str
    user_agent: str
    filename: Optional[str]
    source_page: str
    model_name: Optional[str] = None
