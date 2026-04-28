import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from src.db.clickhouse import ReleasesAnalyticsSchema, get_clickhouse_client
from src.settings.db import ClickHouseSettings

logger = logging.getLogger(__name__)

__all__ = (
    "generate_release_request_analytics",
    "seed_release_request_analytics",
)


CLIENT_VERSIONS = (
    "0.9.8",
    "1.0.0",
    "1.1.4",
    "1.2.0",
    "2.0.0",
    "2.1.3",
    "3.0.0-beta",
)
LATEST_VERSIONS = (
    "1.2.0",
    "2.0.0",
    "2.1.3",
    "2.2.0",
    "3.0.0-beta",
)
USER_AGENTS = (
    "ReleaseAgentClient/1.0",
    "ReleaseAgentClient/2.0",
    "curl/8.7.1",
    "python-httpx/0.28",
    "Mozilla/5.0 ReleaseChecker",
)
RESPONSE_STATUSES = (200, 200, 200, 200, 304, 404, 500)


def _random_timestamp(
    rng: random.Random,
    *,
    now: datetime,
    days_range: int,
) -> datetime:
    start = now - timedelta(days=days_range)
    seconds_range = days_range * 2 * 24 * 60 * 60
    return start + timedelta(seconds=rng.randint(0, seconds_range))


def _random_ref_url(rng: random.Random, *, ignore_domain: str) -> str | None:
    external_hosts = [
        f"customer-{rng.randint(1, 80)}.example.test",
        f"team-{rng.randint(1, 40)}.company.test",
        f"workspace-{rng.randint(1, 25)}.releases.test",
    ]
    internal_hosts = [ignore_domain.strip().lower()] if ignore_domain.strip() else []
    host = rng.choice(external_hosts + internal_hosts + [""])
    if not host:
        return None

    scheme = rng.choice(("https", "http"))
    path = rng.choice(("/downloads", "/releases", "/updates/check", "/"))
    return f"{scheme}://{host}{path}"


def generate_release_request_analytics(
    *,
    rows: int,
    days_range: int,
    ignore_domain: str,
    random_seed: int | None = None,
    now: datetime | None = None,
) -> list[ReleasesAnalyticsSchema]:
    """Generate synthetic release request analytics rows for local verification.

    The timestamps are distributed between ``now - days_range`` and
    ``now + days_range``. Pass ``random_seed`` to make the generated dataset
    deterministic across runs.
    """
    rng = random.Random(random_seed)
    now = now or datetime.now(UTC)
    install_ids_count = max(rows // 5, 1)

    return [
        ReleasesAnalyticsSchema(
            timestamp=_random_timestamp(rng, now=now, days_range=days_range),
            client_version=rng.choice(CLIENT_VERSIONS + (None,)),
            client_install_id=f"install-{rng.randint(1, install_ids_count):05d}",
            client_is_corporate=rng.choice((True, False, None)),
            client_is_internal=rng.choice((False, False, False, True)),
            client_ip_address=f"198.51.100.{rng.randint(1, 254)}",
            client_user_agent=rng.choice(USER_AGENTS),
            client_ref_url=_random_ref_url(rng, ignore_domain=ignore_domain),
            response_latest_version=rng.choice(LATEST_VERSIONS + (None,)),
            response_status=rng.choice(RESPONSE_STATUSES),
            response_time_ms=round(rng.uniform(8, 1500), 2),
            response_from_cache=rng.choice((True, False)),
        )
        for _ in range(rows)
    ]


async def seed_release_request_analytics(
    settings: ClickHouseSettings,
    *,
    rows: int,
    days_range: int,
    random_seed: int | None = None,
) -> int:
    """Insert generated release request analytics rows into ClickHouse.

    This helper assumes the ClickHouse connection is already initialized. It is
    intended for explicit CLI/Make usage and returns the number of inserted rows.
    """
    if rows <= 0:
        return 0

    generated_rows = generate_release_request_analytics(
        rows=rows,
        days_range=days_range,
        ignore_domain=settings.ignore_domain,
        random_seed=random_seed,
    )
    if not generated_rows:
        return 0

    column_names = list(ReleasesAnalyticsSchema.model_fields)
    data: list[list[Any]] = []
    for row in generated_rows:
        row_data = row.model_dump()
        data.append([row_data[column] for column in column_names])

    client = await get_clickhouse_client()
    await client.insert(
        table=settings.analytics_table_name,
        data=data,
        column_names=column_names,
    )
    logger.info(
        "[AnalyticsSeed] Inserted %d synthetic release request rows into ClickHouse",
        len(data),
    )
    return len(data)
