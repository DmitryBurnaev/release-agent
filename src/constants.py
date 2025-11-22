from enum import StrEnum
from pathlib import Path
from typing import Self


class StingEnum(StrEnum):
    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls[value.upper()]


APP_DIR = Path(__file__).parent
RENDER_KW = {"class": "form-control"}
RENDER_KW_REQ = RENDER_KW | {"required": True}
CACHE_KEY_ACTIVE_RELEASES = "active_releases"
CACHE_KEY_ACTIVE_RELEASES_PAGE = "active_releases_page_{offset}_{limit}"
CACHE_TTL_ACTIVE_RELEASES = 3600 * 24 * 14  # 14 days
