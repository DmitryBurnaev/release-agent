# AGENTS.md

Guidance for future coding agents working in this repository.

## Project Shape

This is a small FastAPI application for managing release descriptions through an admin UI and serving them through public/authenticated APIs. Public release requests are logged to ClickHouse for analytics.

Main areas:

- `src/main.py` - FastAPI app factory, lifespan, route/static mounting.
- `src/modules/api/` - public and authenticated API routers.
- `src/modules/admin/` - SQLAdmin app, views, templates, local admin static assets.
- `src/db/` - PostgreSQL session/repositories and ClickHouse connector/schema.
- `src/services/` - cache, analytics, proxy, counters, helper services.
- `src/modules/cli/` - Click-based management commands.
- `src/tests/` - pytest suite.

## Working Rules

- Prefer small, scoped changes. Do not mix unrelated cleanup with feature work.
- Do not revert user changes in a dirty tree. Check `git status --short --untracked-files=all` before editing.
- Use `rg`/`rg --files` for search.
- Use `apply_patch` for manual edits.
- Keep test or demo data generation out of app startup and runtime production paths. Use explicit CLI/Make commands instead.
- Avoid putting hostnames, IPs, personal paths, prod domains, or one-off debug values into committed code.
- The project targets Python 3.13 and uses `uv`.

## Commands

Common commands:

```bash
make install
make format
make lint
make test
make run
```

Direct checks often used during focused work:

```bash
uv run ruff check <paths>
uv run black --check <paths>
uv run mypy <paths>
uv run env LOG_FORMAT='[%(levelname)s] %(message)s' pytest <paths>
```

Local environment note: if tests fail during app creation with `Invalid format 'json' for '%' style`, rerun tests with a safe `LOG_FORMAT`, for example:

```bash
uv run env LOG_FORMAT='[%(levelname)s] %(message)s' pytest
```

## CLI

Management commands live in `src/modules/cli/management.py` and are implemented with Click.

Examples:

```bash
uv run python -m src.modules.cli.management --help
uv run python -m src.modules.cli.management change-admin-password --help
uv run python -m src.modules.cli.management seed-analytics --help
```

Fake analytics data is intentionally a manual command, not a startup hook:

```bash
make seed-analytics
make seed-analytics ANALYTICS_SEED_ROWS=1000 ANALYTICS_SEED_DAYS_RANGE=30
make seed-analytics ANALYTICS_SEED_ROWS=1000 ANALYTICS_SEED_RANDOM_SEED=42
```

## ClickHouse And Analytics

- ClickHouse settings use the `CH_` prefix in `src/settings/db.py`.
- The analytics table schema is `ReleasesAnalyticsSchema` in `src/db/clickhouse.py`.
- Request logging goes through `AnalyticsService` in `src/services/analytics.py`.
- Synthetic analytics data generation is in `src/services/analytics_seed.py` and should stay manually invoked via CLI/Make.
- Admin ClickHouse iframe pages use `src/modules/admin/templates/analytics.html`.
- The template should not embed ClickHouse default dashboard queries. If custom queries are not passed in the template context, leave ClickHouse's built-in dashboard untouched.
- API-only SQLAdmin views must be hidden from the sidebar with `is_visible() -> False`.

## Admin UI Notes

- SQLAdmin views are registered in `src/modules/admin/app.py`.
- Templates live in `src/modules/admin/templates/`.
- Local admin JS/CSS assets are served from `src/modules/admin/static/` through `/js` and `/css` mounts in `src/main.py`.
- Release editor templates use local Toast UI assets; avoid reintroducing CDN dependencies unless explicitly requested.

## Testing Guidance

- Add focused tests near the touched behavior.
- For admin view context tests, patch `get_app_settings` and `get_clickhouse_settings` at the module under test.
- For ClickHouse insert/query behavior, mock `get_clickhouse_client`; do not require a live ClickHouse in unit tests.
- After CLI changes, run at least:

```bash
uv run env LOG_FORMAT='[%(levelname)s] %(message)s' pytest src/tests/units/cli
```

After analytics/admin changes, run at least:

```bash
uv run env LOG_FORMAT='[%(levelname)s] %(message)s' pytest src/tests/units/admin src/tests/units/test_analytics_seed.py
```

## Git And Review

- Commit style on the feature branch commonly uses:

```text
[#18] Add some CH using improvements: short action summary

- detail
- detail
```

- Review should prioritize real bugs/regressions over style.
- Before finalizing, inspect `git diff --check` and scan diffs for debug logs, test-only branches, hardcoded deployment values, local paths, domains, or IPs.
