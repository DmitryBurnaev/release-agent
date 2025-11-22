import datetime
import logging
import contextvars
from typing import TypedDict, Optional

from src.settings.app import get_app_settings

logger = logging.getLogger(__name__)
alert_context_var: contextvars.ContextVar[Optional["ErrorInContext"]] = contextvars.ContextVar(
    "alert_context", default=None
)


class ErrorInContext(TypedDict):
    title: str
    details: str


def register_error_alert(title: str, details: str) -> None:
    """
    Register an error alert in the context
    """
    logger.debug("Registering error alert: title=%s, details=%s", title, details)
    alert_context_var.set(ErrorInContext(title=title, details=details))


def get_current_error_alert() -> dict[str, str] | None:
    """
    Get the current error alert from the context (used for global context in jinja templates)
    """
    current_error = alert_context_var.get()
    if current_error is None:
        return None

    return {
        "title": current_error["title"],
        "details": current_error["details"],
    }


def _format_datetime(value: datetime.datetime | None, dt_format: str, blank: str) -> str:
    if not value:
        return blank

    ui_timezone = get_app_settings().ui_timezone
    if ui_timezone is not None:
        value = value.replace(tzinfo=datetime.timezone.utc).astimezone(ui_timezone)

    return value.strftime(dt_format)


def format_datetime(value: datetime.datetime, blank: str = "-") -> str:
    """
    Format a datetime object to a string in the format "%d.%m.%Y %H:%M"
    """
    return _format_datetime(value, dt_format="%d.%m.%Y %H:%M", blank=blank)


def format_date(value: datetime.datetime, blank: str = "-") -> str:
    """
    Format a datetime object to a string in the format "%d.%m.%Y"
    """
    return _format_datetime(value, dt_format="%d.%m.%Y", blank=blank)
