"""Explicit, repeatable PostgreSQL release seeding command."""

import asyncio
from datetime import datetime
from typing import Any

import click
from sqlalchemy.dialects.postgresql import insert

from src.db import Release, close_database, initialize_database
from src.db.session import get_session_factory
from src.db.redis import close_redis, initialize_redis
from src.services.cache import invalidate_release_cache
from src.settings import get_app_settings


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse a calendar version with two releases per month."""
    try:
        year, month, patch = map(int, value.split("."))
        datetime(year, month, 1)
        if patch not in (1, 2):
            raise ValueError
    except (ValueError, OverflowError) as exc:
        raise ValueError("Expected YEAR.MONTH.PATCH, with month 1–12 and patch 1–2") from exc
    return year, month, patch


def generate_releases(start: str, end: str) -> list[dict[str, Any]]:
    """Generate an inclusive range with publication dates on the 1st and 15th."""
    first = parse_version(start)
    last = parse_version(end)
    if first > last:
        raise ValueError("Start version must not be greater than end version")

    rows = []
    year, month, patch = first
    while (year, month, patch) <= last:
        version = f"{year}.{month}.{patch}"
        rows.append(
            {
                "version": version,
                "notes": f"# Release {version}\n\nSynthetic release for testing.\n",
                "url": "",
                "is_active": True,
                "published_at": datetime(year, month, 1 if patch == 1 else 15),
            }
        )
        if (year, month, patch) == last:
            break
        if patch == 1:
            patch = 2
        else:
            patch = 1
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return rows


async def seed_releases(rows: list[dict[str, Any]]) -> int:
    """Insert only missing versions in one transaction, then clear shared cache."""
    await initialize_database()
    try:
        async with get_session_factory().begin() as session:
            statement = (
                insert(Release)
                .values(rows)
                .on_conflict_do_nothing(index_elements=[Release.version])
                .returning(Release.version)
            )
            inserted = len((await session.scalars(statement)).all())
    finally:
        await close_database()

    if get_app_settings().flags.use_redis:
        try:
            await initialize_redis()
            await invalidate_release_cache()
        finally:
            await close_redis()
    return inserted


@click.command(
    "seed-releases", help="Insert active releases, two per month; skip existing versions."
)
@click.option("--start", default="2023.1.1", show_default=True)
@click.option("--end", default="2026.9.2", show_default=True)
def seed_releases_command(start: str, end: str) -> None:
    try:
        rows = generate_releases(start, end)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    inserted = asyncio.run(seed_releases(rows))
    click.echo(f"Releases: {len(rows)}, inserted: {inserted}, skipped: {len(rows) - inserted}")
    click.echo("If the server uses in-memory cache, restart it to refresh cached release pages.")


if __name__ == "__main__":
    seed_releases_command()
