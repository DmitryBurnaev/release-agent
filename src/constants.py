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
