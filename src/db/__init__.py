"""Database module for the application."""

from src.db.dependencies import get_db_session, get_transactional_session, get_uow_with_session
from src.db.models import BaseModel, Product, User, Token, Release
from src.db.repositories import (
    ProductRepository,
    UserRepository,
    TokenRepository,
    ReleaseRepository,
)
from src.db.services import SASessionUOW
from src.db.session import get_session_factory, initialize_database, close_database

__all__ = (
    # Models
    "BaseModel",
    "Product",
    "User",
    "Token",
    "Release",
    # Repositories
    "UserRepository",
    "TokenRepository",
    "ProductRepository",
    "ReleaseRepository",
    # Services
    "SASessionUOW",
    # Session management
    "get_session_factory",
    "initialize_database",
    "close_database",
    "get_db_session",
    "get_transactional_session",
    "get_uow_with_session",
)
