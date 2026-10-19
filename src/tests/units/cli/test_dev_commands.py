import asyncio
from collections import Counter
from datetime import datetime
from ipaddress import ip_address, ip_network
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2 as httpx
import pytest
from click.testing import CliRunner
from sqlalchemy.dialects import postgresql

from src.modules.cli.load_test import LoadResult, RequestMix, load_test_command, run_load
from src.modules.cli.management import cli
from src.modules.cli.seed_releases import generate_releases, seed_releases


@pytest.fixture(autouse=True)
def test_app() -> None:
    """These command tests use mocked DB/HTTP and need no running app or database."""


def test_generate_default_releases() -> None:
    rows = generate_releases("2023.1.1", "2026.9.2")
    assert len(rows) == len({row["version"] for row in rows}) == 90
    assert rows[0]["version"] == "2023.1.1"
    assert rows[-1]["version"] == "2026.9.2"
    assert [row["version"] for row in rows[22:26]] == [
        "2023.12.1",
        "2023.12.2",
        "2024.1.1",
        "2024.1.2",
    ]
    assert all(row["is_active"] for row in rows)
    dates = [row["published_at"] for row in rows]
    assert dates == sorted(dates)
    assert dates[0] == datetime(2023, 1, 1)
    assert dates[-1] == datetime(2026, 9, 15)


def test_generate_partial_months_and_single_release() -> None:
    assert [row["version"] for row in generate_releases("2024.12.2", "2025.1.1")] == [
        "2024.12.2",
        "2025.1.1",
    ]
    assert len(generate_releases("2026.9.2", "2026.9.2")) == 1


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026.10.1", "2026.9.2"),
        ("2023.0.1", "2026.9.2"),
        ("2023.13.1", "2026.9.2"),
        ("2023.1.0", "2026.9.2"),
        ("2023.1.1", "2026.9.3"),
        ("no-version", "2026.9.2"),
    ],
)
def test_invalid_release_range(start: str, end: str) -> None:
    with pytest.raises(ValueError):
        generate_releases(start, end)


@pytest.mark.parametrize("inserted", [0, 2])
async def test_seed_inserts_atomically_without_overwriting_existing_versions(inserted: int) -> None:
    rows = generate_releases("2026.9.1", "2026.9.2")
    session = AsyncMock()
    session.scalars.return_value = MagicMock()
    session.scalars.return_value.all.return_value = ["version"] * inserted
    factory = MagicMock()
    factory.begin.return_value.__aenter__.return_value = session
    settings = MagicMock()
    settings.flags.use_redis = True
    with (
        patch("src.modules.cli.seed_releases.initialize_database"),
        patch("src.modules.cli.seed_releases.close_database") as close,
        patch("src.modules.cli.seed_releases.get_session_factory", return_value=factory),
        patch("src.modules.cli.seed_releases.get_app_settings", return_value=settings),
        patch("src.modules.cli.seed_releases.initialize_redis") as init_redis,
        patch("src.modules.cli.seed_releases.close_redis") as close_redis,
        patch("src.modules.cli.seed_releases.invalidate_release_cache") as invalidate,
    ):
        assert await seed_releases(rows) == inserted
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (version) DO NOTHING" in compiled
    assert "RETURNING releases.version" in compiled
    factory.begin.return_value.__aexit__.assert_awaited_once_with(None, None, None)
    close.assert_awaited_once()
    init_redis.assert_awaited_once()
    invalidate.assert_awaited_once()
    close_redis.assert_awaited_once()


async def test_seed_closes_database_on_failure_without_invalidating_cache() -> None:
    factory = MagicMock()
    factory.begin.return_value.__aenter__.side_effect = RuntimeError("Database unavailable")
    with (
        patch("src.modules.cli.seed_releases.initialize_database"),
        patch("src.modules.cli.seed_releases.close_database") as close,
        patch("src.modules.cli.seed_releases.get_session_factory", return_value=factory),
        patch("src.modules.cli.seed_releases.initialize_redis") as init_redis,
    ):
        with pytest.raises(RuntimeError, match="Database unavailable"):
            await seed_releases(generate_releases("2026.9.1", "2026.9.2"))
    close.assert_awaited_once()
    init_redis.assert_not_awaited()


async def test_seed_does_not_require_redis_for_memory_cache() -> None:
    factory = MagicMock()
    session = factory.begin.return_value.__aenter__.return_value
    session.scalars.return_value = MagicMock()
    session.scalars.return_value.all.return_value = []
    settings = MagicMock()
    settings.flags.use_redis = False
    with (
        patch("src.modules.cli.seed_releases.initialize_database"),
        patch("src.modules.cli.seed_releases.close_database"),
        patch("src.modules.cli.seed_releases.get_session_factory", return_value=factory),
        patch("src.modules.cli.seed_releases.get_app_settings", return_value=settings),
        patch("src.modules.cli.seed_releases.initialize_redis") as init_redis,
    ):
        assert await seed_releases(generate_releases("2026.9.1", "2026.9.2")) == 0
    init_redis.assert_not_awaited()


def test_seed_cli_defaults_and_invalid_input() -> None:
    with patch("src.modules.cli.seed_releases.seed_releases", return_value=90) as seed:
        result = CliRunner().invoke(cli, ["seed-releases"])
        assert result.exit_code == 0, result.output
        assert "Releases: 90, inserted: 90, skipped: 0" in result.output
        assert len(seed.call_args.args[0]) == 90
        seed.reset_mock()
        result = CliRunner().invoke(cli, ["seed-releases", "--start", "invalid"])
        assert result.exit_code == 2
        seed.assert_not_called()


@pytest.mark.parametrize("requests,concurrency", [(100_000, 20), (43, 3), (3, 20), (5, 1)])
async def test_load_exact_count_and_concurrency_limit(requests: int, concurrency: int) -> None:
    active = peak = calls = 0
    install_counts = Counter()
    versions = set()
    user_agents = set()
    ips = set()
    flags = set()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak, calls
        active += 1
        peak = max(peak, active)
        calls += 1
        install_counts[request.url.params["install_id"]] += 1
        versions.add(request.url.params["current_version"])
        user_agents.add(request.headers["user-agent"])
        ips.add(request.headers["x-forwarded-for"])
        flags.add((request.url.params["is_corporate"], request.url.params["is_internal"]))
        await asyncio.sleep(0)
        active -= 1
        return httpx.Response(200, json={"items": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("src.modules.cli.load_test.httpx.AsyncClient", return_value=client) as client_cls:
        result = await run_load(
            "https://load.example.test/public/releases/", requests, concurrency, progress_every=0
        )
    assert result.completed == result.successful == calls == requests
    assert result.statuses == {200: requests}
    assert result.errors == {}
    assert peak == min(concurrency, requests)
    assert result.elapsed > 0
    assert len(install_counts) == result.installations == min(requests, 1_000)
    assert max(install_counts.values()) - min(install_counts.values()) <= 1
    if requests == 100_000:
        assert set(install_counts.values()) == {100}
        assert len(versions) == 90
        assert len(user_agents) > 1
        assert len(ips) > 1
        assert len(flags) == 4
    assert client.is_closed
    limits = client_cls.call_args.kwargs["limits"]
    assert limits.max_connections == limits.max_keepalive_connections == concurrency


def test_request_mix_is_repeatable_independently_of_generation_order() -> None:
    mix = RequestMix(1_000, random_seed=42)
    repeat = RequestMix(1_000, random_seed=42)
    different = RequestMix(1_000, random_seed=43)
    assert len(set(mix.install_ids)) == 1_000
    assert mix.install_ids == repeat.install_ids
    assert mix.install_ids != different.install_ids
    expected = {index: mix.for_request(index) for index in range(25)}
    for index in reversed(range(25)):
        assert repeat.for_request(index) == expected[index]
    assert mix.for_request(1_000)[0]["install_id"] == mix.for_request(0)[0]["install_id"]


def test_request_mix_uses_valid_synthetic_headers_and_varied_metadata() -> None:
    mix = RequestMix(10, random_seed=42)
    networks = [
        ip_network(value) for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
    ]
    languages = set()
    referers = set()
    pagination = set()
    missing_referer = False
    for index in range(1_000):
        params, headers = mix.for_request(index)
        ip = ip_address(headers["X-Forwarded-For"])
        assert any(ip in network for network in networks)
        assert headers["X-Real-IP"] == str(ip)
        assert headers["Forwarded"] == f"for={ip}"
        assert headers["Accept"] == "application/json"
        assert params["is_corporate"] in ("true", "false")
        assert params["is_internal"] in ("true", "false")
        assert int(params["offset"]) >= 0
        assert 1 <= int(params["limit"]) <= 100
        languages.add(headers["Accept-Language"])
        pagination.add((params["offset"], params["limit"]))
        if "Referer" in headers:
            assert httpx.URL(headers["Referer"]).host.endswith(".example.test")
            referers.add(headers["Referer"])
        else:
            missing_referer = True
    assert len(languages) > 1
    assert len(referers) > 1
    assert len(pagination) > 1
    assert missing_referer


async def test_load_merges_generated_query_and_keeps_unrelated_parameters() -> None:
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("src.modules.cli.load_test.httpx.AsyncClient", return_value=client):
        result = await run_load(
            "https://load.example.test/public/releases/?install_id=fixed&source=load&source=test",
            requests=11,
            concurrency=3,
            installations=4,
            random_seed=42,
            progress_every=0,
        )
    expected_mix = RequestMix(4, random_seed=42)
    expected = {tuple(sorted(expected_mix.for_request(index)[0].items())) for index in range(11)}
    actual = set()
    for request in seen:
        assert request.url.params.get_list("source") == ["load", "test"]
        assert request.url.params.get_list("install_id") != ["fixed"]
        assert len(request.url.params.get_list("install_id")) == 1
        actual.add(
            tuple(
                sorted((key, value) for key, value in request.url.params.items() if key != "source")
            )
        )
    assert actual == expected
    assert result.installations == 4


async def test_load_counts_http_and_transport_errors_without_retries() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("Connection failed", request=request)
        return httpx.Response([0, 200, 404, 500, 302][calls - 1])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("src.modules.cli.load_test.httpx.AsyncClient", return_value=client):
        result = await run_load("https://load.example.test/", 5, 1, progress_every=0)
    assert calls == result.completed == 5
    assert result.successful == 1
    assert result.statuses == {200: 1, 404: 1, 500: 1, 302: 1}
    assert result.errors == {"ConnectError": 1}


async def test_load_enforces_total_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("src.modules.cli.load_test.httpx.AsyncClient", return_value=client):
        result = await run_load("https://load.example.test/", 3, 2, timeout=0.01, progress_every=0)
    assert result.completed == 3
    assert result.successful == 0
    assert result.errors == {"TimeoutError": 3}


@pytest.mark.parametrize("failed", [False, True])
def test_load_cli_reports_summary_and_failure_exit_status(failed: bool) -> None:
    summary = LoadResult(
        completed=100_000,
        statuses=Counter({200: 99_999 if failed else 100_000}),
        errors=Counter({"ReadTimeout": 1}) if failed else Counter(),
        elapsed=10,
        installations=1_000,
    )
    with patch("src.modules.cli.load_test.run_load", return_value=summary) as load:
        result = CliRunner().invoke(cli, ["load-test", "--url", "https://load.example.test/"])
    assert result.exit_code == int(failed), result.output
    assert "Completed: 100000" in result.output
    assert "requests/s: 10000.00" in result.output
    assert "Unique installation IDs (attempts): 1000" in result.output
    load.assert_awaited_once_with(
        "https://load.example.test/",
        100_000,
        20,
        30.0,
        5_000,
        installations=1_000,
        random_seed=None,
    )


def test_load_cli_passes_installation_count_and_random_seed() -> None:
    with patch("src.modules.cli.load_test.run_load", return_value=LoadResult()) as load:
        result = CliRunner().invoke(
            cli,
            [
                "load-test",
                "--url",
                "https://load.example.test/",
                "--installations",
                "25",
                "--random-seed",
                "0",
            ],
        )
    assert result.exit_code == 0, result.output
    load.assert_awaited_once_with(
        "https://load.example.test/",
        100_000,
        20,
        30.0,
        5_000,
        installations=25,
        random_seed=0,
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--concurrency", "0"],
        ["--concurrency", "21"],
        ["--installations", "0"],
        ["--requests", "0"],
        ["--timeout", "0"],
        ["--progress-every", "-1"],
        ["--url", "file:///tmp/load-test"],
        ["--url", "missing-scheme"],
    ],
)
def test_load_cli_rejects_invalid_options(args: list[str]) -> None:
    with patch("src.modules.cli.load_test.run_load") as load:
        result = CliRunner().invoke(
            load_test_command, ["--url", "https://load.example.test/", *args]
        )
    assert result.exit_code == 2, result.output
    load.assert_not_called()
