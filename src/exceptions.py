import logging

from fastapi import status


class BaseApplicationError(Exception):
    """Base application error"""

    log_level: int = logging.ERROR
    log_message: str = "Application error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AppSettingsError(BaseApplicationError):
    """Settings error"""


class StartupError(BaseApplicationError):
    """Startup error"""


class DatabaseError(BaseApplicationError):
    """Database error"""


class InstanceLookupError(BaseApplicationError):
    """Instance lookup error"""

    log_level: int = logging.WARNING
    log_message: str = "Instance not found"
    status_code: int = status.HTTP_404_NOT_FOUND


class ReleaseRequestError(BaseApplicationError):
    """Release request error"""

    log_level: int = logging.WARNING
    log_message: str = "Release request error"
    status_code: int = status.HTTP_400_BAD_REQUEST


class CacheBackendError(BaseApplicationError):
    """Cache access error"""

    log_level: int = logging.ERROR
    log_message: str = "Unable to use cache backend"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
