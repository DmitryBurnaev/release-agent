from datetime import datetime
import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column, backref

from src.utils import utcnow
from src.modules.auth.hashers import PBKDF2PasswordHasher

logger = logging.getLogger(__name__)


class BaseModel(AsyncAttrs, DeclarativeBase):
    id: Mapped[int]


class User(BaseModel):
    """Users table for an authorization process"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(128), unique=True)
    password: Mapped[str] = mapped_column(sa.String(128))
    email: Mapped[str] = mapped_column(sa.String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @classmethod
    def make_password(cls, raw_password: str) -> str:
        hasher = PBKDF2PasswordHasher()
        return hasher.encode(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        hasher = PBKDF2PasswordHasher()
        verified, _ = hasher.verify(raw_password, encoded=str(self.password))
        return verified

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    def __str__(self) -> str:
        return f"User '{self.username}'"

    def __repr__(self) -> str:
        return (
            f"User("
            f"login='{self.username}', "
            f"email='{self.email}'"
            f"is_active='{self.is_active}'"
            f"is_admin='{self.is_admin}')"
        )


class Token(BaseModel):
    """Simple token storage for authorizing and API usages"""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(sa.String(128))
    token: Mapped[str] = mapped_column(sa.String(512), unique=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=True, onupdate=utcnow)

    # relations
    user: Mapped[User] = relationship(
        User,
        backref=backref("tokens", cascade="all, delete-orphan"),
        lazy="joined",
    )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return (
            f"Token("
            f"id={self.id}, "
            f"name={self.name}, "
            f"user_id={self.user_id}, "
            f"token='[MASKED]', "
            f"expires_at={self.expires_at}, "
            f"created_at={self.created_at}, "
            f"updated_at={self.updated_at}"
            f")"
        )

    @property
    def raw_token(self) -> str | None:
        return getattr(self, "__raw_token", None)

    @raw_token.setter
    def raw_token(self, value: str) -> None:
        setattr(self, "__raw_token", value)


class Product(BaseModel):
    """A product with its own independently versioned releases."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    releases: Mapped[list["Release"]] = relationship(back_populates="product")

    def __str__(self) -> str:
        return self.name


class Release(BaseModel):
    """Release model representing a release in the system."""

    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(sa.ForeignKey("products.id"), nullable=False)
    version: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    notes: Mapped[str] = mapped_column(sa.Text, nullable=False)
    url: Mapped[str] = mapped_column(sa.String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    published_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=True, onupdate=utcnow)

    product: Mapped[Product] = relationship(back_populates="releases", lazy="joined")

    __table_args__ = (sa.UniqueConstraint("product_id", "version"),)

    @property
    def product_name(self) -> str:
        """Return the product name for API serialization."""
        return self.product.name

    def __str__(self) -> str:
        return f"Release '{self.version}'"

    def __repr__(self) -> str:
        return f"Release(id={self.id!r}, version={self.version!r}, is_active={self.is_active})"
