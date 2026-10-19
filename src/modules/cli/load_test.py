"""Bounded asynchronous GET load generator; no database connection needed."""

import asyncio
import random
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from urllib.parse import urlsplit
from uuid import UUID

import click
import httpx2 as httpx

CLIENT_VERSIONS = tuple(
    f"{year}.{month}.{patch}"
    for year in range(2023, 2027)
    for month in range(1, 10 if year == 2026 else 13)
    for patch in (1, 2)
)
USER_AGENTS = (
    "ReleaseAgentClient/1.0 (Linux; x86_64)",
    "ReleaseAgentClient/2.0 (Windows; x86_64)",
    "ReleaseAgentClient/2.0 (macOS; arm64)",
    "curl/8.7.1",
    "Mozilla/5.0 ReleaseChecker",
)
LANGUAGES = ("en-US,en;q=0.9", "ru-RU,ru;q=0.9", "de-DE,de;q=0.9", "fr-FR,fr;q=0.9")
# Documentation-only ranges: synthetic addresses never represent real clients.
IP_PREFIXES = ("192.0.2", "198.51.100", "203.0.113")


class RequestMix:
    """Generate repeatable request data with an evenly used, shuffled pool of IDs."""

    def __init__(self, installations: int, random_seed: int | None = None) -> None:
        if installations < 1:
            raise ValueError("Installation count must be positive")
        rng = random.Random(random_seed)
        run_id = UUID(int=rng.getrandbits(128), version=4).hex
        self.install_ids = [f"load-{run_id}-{index + 1:06d}" for index in range(installations)]
        rng.shuffle(self.install_ids)
        self._request_seed = rng.getrandbits(128)

    def for_request(self, index: int) -> tuple[dict[str, str], dict[str, str]]:
        # Index-based randomness keeps the workload independent of completion order.
        rng = random.Random(self._request_seed + index)
        params = {
            "install_id": self.install_ids[index % len(self.install_ids)],
            "current_version": rng.choice(CLIENT_VERSIONS),
            "is_corporate": rng.choice(("true", "false")),
            "is_internal": rng.choice(("true", "false", "false", "false")),
            "offset": str(rng.choice((0, 10, 20, 40, 60, 80))),
            "limit": str(rng.choice((10, 20, 50, 100))),
        }
        ip = f"{rng.choice(IP_PREFIXES)}.{rng.randint(1, 254)}"
        headers = {
            "User-Agent": rng.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": rng.choice(LANGUAGES),
            "X-Forwarded-For": ip,
            "X-Real-IP": ip,
            "Forwarded": f"for={ip}",
        }
        if rng.randrange(5):
            host = f"{rng.choice(('portal', 'downloads', 'updates'))}-{rng.randint(1, 50)}"
            path = rng.choice(("releases", "downloads", "updates/check"))
            headers["Referer"] = f"https://{host}.example.test/{path}"
        return params, headers


@dataclass
class LoadResult:
    completed: int = 0
    statuses: Counter[int] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    elapsed: float = 0.0
    installations: int = 0

    @property
    def successful(self) -> int:
        return sum(count for status, count in self.statuses.items() if 200 <= status < 300)


async def run_load(
    url: str,
    requests: int = 100_000,
    concurrency: int = 20,
    timeout: float = 30.0,
    progress_every: int = 5_000,
    installations: int = 1_000,
    random_seed: int | None = None,
) -> LoadResult:
    """Make exactly N attempts with at most 20 workers and reusable connections."""
    if requests < 1 or not 1 <= concurrency <= 20 or timeout <= 0 or progress_every < 0:
        raise ValueError("Invalid request count, concurrency, timeout, or progress interval")
    mix = RequestMix(min(installations, requests), random_seed)
    base_url = httpx.URL(url)
    result = LoadResult(installations=len(mix.install_ids))
    started = perf_counter()
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
        timeout=timeout,
        follow_redirects=False,
    ) as client:

        async def worker(worker_id: int) -> None:
            for index in range(worker_id, requests, concurrency):
                params, headers = mix.for_request(index)
                request_url = base_url.copy_merge_params(params)
                try:
                    # Also bound the total request duration, including reading the body.
                    async with asyncio.timeout(timeout):
                        response = await client.get(request_url, headers=headers)
                    result.statuses[response.status_code] += 1
                except (httpx.RequestError, TimeoutError) as exc:
                    result.errors[type(exc).__name__] += 1
                result.completed += 1
                if progress_every and result.completed % progress_every == 0:
                    click.echo(
                        f"Completed: {result.completed}/{requests}, "
                        f"successful: {result.successful}, "
                        f"failed: {result.completed - result.successful}"
                    )

        async with asyncio.TaskGroup() as group:
            for worker_id in range(min(concurrency, requests)):
                group.create_task(worker(worker_id))
    result.elapsed = perf_counter() - started
    return result


@click.command("load-test", help="Send many GET requests to a full endpoint URL.")
@click.option("--url", required=True, help="Full HTTP(S) endpoint URL, including query parameters.")
@click.option("--requests", default=100_000, show_default=True, type=click.IntRange(min=1))
@click.option("--concurrency", default=20, show_default=True, type=click.IntRange(1, 20))
@click.option(
    "--installations",
    default=1_000,
    show_default=True,
    type=click.IntRange(min=1),
    help="Unique installation IDs; capped at the request count for smoke tests.",
)
@click.option("--random-seed", type=int, default=None, help="Reproduce the generated request mix.")
@click.option(
    "--timeout", default=30.0, show_default=True, type=click.FloatRange(min=0, min_open=True)
)
@click.option(
    "--progress-every",
    default=5_000,
    show_default=True,
    type=click.IntRange(min=0),
    help="Report every N completed requests; 0 disables progress output.",
)
def load_test_command(
    url: str,
    requests: int,
    concurrency: int,
    timeout: float,
    progress_every: int,
    installations: int,
    random_seed: int | None,
) -> None:
    try:
        parsed = urlsplit(url)
        valid_url = parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        valid_url = False
    if not valid_url:
        raise click.BadParameter("Expected a full HTTP(S) URL", param_hint="--url")
    result = asyncio.run(
        run_load(
            url,
            requests,
            concurrency,
            timeout,
            progress_every,
            installations=installations,
            random_seed=random_seed,
        )
    )
    click.echo(
        f"Completed: {result.completed}, successful (2xx): {result.successful}, "
        f"failed: {result.completed - result.successful}"
    )
    click.echo(
        f"Elapsed: {result.elapsed:.2f}s, "
        f"requests/s: {result.completed / result.elapsed if result.elapsed else 0:.2f}"
    )
    click.echo(f"HTTP statuses: {dict(sorted(result.statuses.items()))}")
    click.echo(f"Transport errors: {dict(result.errors)}")
    click.echo(f"Unique installation IDs (attempts): {result.installations}")
    if result.completed != result.successful:
        raise click.ClickException("Some requests failed; see the summary above.")


if __name__ == "__main__":
    load_test_command()
