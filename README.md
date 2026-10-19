# Release Agent Application

Small helper for configurable release versions

## Installation

For detailed server installation instructions, see [INSTALL.md](INSTALL.md).

## Development

### Prerequisites

- Docker and Docker Compose
- Python 3.13 (for local development)
- uv package manager (version 0.9.0 or above)

### Fast commands

1. Install venv
    ```shell
    make install
    ```
2. Generate secrets for environment setup
   ```shell
   make secrets
   ```
3. Format changes
   ```shell
   make format
   ```
4. Lint changes 
   ```shell
   make lint
   ```
5. Run tests 
   ```shell
   make test
   ```

## Environment Setup

### Quick Start

1. Copy the environment template:
   ```bash
   cp .env.template .env
   ```

2. Generate secure secrets for your environment:
   ```bash
   make secrets
   ```
   
   This command will automatically:
   - Generate secure random secrets for your application
   - Write them directly to your `.env` file with a "# Generated secrets" comment
   - Set proper file permissions (600) for security
   - Display success messages in the console

   The generated secrets include:
   - `APP_SECRET_KEY` - Secret key for the application
   - `DB_PASSWORD` - Database password
   - `ADMIN_PASSWORD` - Default admin password
   - `CH_PASSWORD` - ClickHouse password

3. Review and update your `.env` file with any additional required settings.

## CLI usages

1. Generate Secrets
   ```bash
   # Generate secure secrets and write them to .env file
   uv run python -m src.cli.generate_secrets
   
   # This will automatically:
   # - Generate random secrets for APP_SECRET_KEY, DB_PASSWORD, ADMIN_PASSWORD
   # - Append them to .env file with "# Generated secrets" comment
   # - Set file permissions to 600 for security
   ```

2. User management (change password)
   ```bash
   # Usage: python -m src.modules.cli.management change-admin-password [OPTIONS]
   # Change the admin password.   
   # Options:
   #   --help                           Show this help message
   #   --username TEXT                  Admin username
   #   --random-password                Generate a random password.
   #   --random-password-length INTEGER Set length of generated random password.

   # Example: change password for admin to auto-generated password with length 32 symbols
   uv run python -m src.modules.cli.management change-admin-password --username admin --random-password --random-password-length 32

   # Example: change password for my-user to password from stdin
   uv run python -m src.modules.cli.management change-admin-password --username my-user
   # ===
   # Changing admin password...
   # Set a new password for my-user
   # New Password: <INPUT>
   # Repeat for confirmation: <INPUT>
   ```

3. Analytics test data
   ```bash
   # Fill ClickHouse release request analytics with fake data.
   # Requires configured CH_* settings and an available ClickHouse instance.
   make seed-analytics

   # Optional overrides:
   make seed-analytics ANALYTICS_SEED_ROWS=1000 ANALYTICS_SEED_DAYS_RANGE=30
   make seed-analytics ANALYTICS_SEED_ROWS=1000 ANALYTICS_SEED_RANDOM_SEED=42

   # Direct Click command:
   uv run python -m src.modules.cli.management seed-analytics --rows 1000 --days-range 30
   ```


4. Sequential releases in PostgreSQL

   ```bash
   make seed-releases
   # Optional inclusive range (YEAR.MONTH.PATCH, patch is 1 or 2):
   make seed-releases RELEASES_SEED_START=2023.1.1 RELEASES_SEED_END=2026.9.2

   # Direct Click command:
   uv run python -m src.modules.cli.management seed-releases --start 2023.1.1 --end 2026.9.2
   ```

   Requires configured `DB_*` settings and applied migrations. Creates 90 active releases
   by default, two per month, published on the 1st and 15th. Existing versions are
   skipped without changing their contents or activation state. Redis cache is cleared
   using the application's settings; Redis must be available when `FLAG_USE_REDIS=true`.
   With in-memory cache, restart the running server after seeding.

5. HTTP load test

   Set `RELEASES_URL` to the full endpoint URL, ending in `/public/releases/`.

   ```bash
   make load-test RELEASES_URL="$RELEASES_URL"
   make load-test RELEASES_URL="$RELEASES_URL" LOAD_TEST_REQUESTS=150000 LOAD_TEST_CONCURRENCY=10 LOAD_TEST_TIMEOUT=30 LOAD_TEST_PROGRESS_EVERY=10000
   # Repeatable mix of 100,000 requests from exactly 1,000 installation IDs:
   make load-test RELEASES_URL="$RELEASES_URL" LOAD_TEST_INSTALLATIONS=1000 LOAD_TEST_RANDOM_SEED=42

   # Direct Click command:
   uv run python -m src.modules.cli.management load-test --url "$RELEASES_URL" --installations 1000 --random-seed 42
   ```

   Both Make targets run the existing Click commands via `uv run python` and require `.env`,
   like the other management targets. `LOAD_TEST_REQUESTS`, `LOAD_TEST_CONCURRENCY`,
   `LOAD_TEST_TIMEOUT`, and `LOAD_TEST_PROGRESS_EVERY` default to 100000, 20, 30, and 5000.
   `LOAD_TEST_INSTALLATIONS` defaults to 1000; `LOAD_TEST_RANDOM_SEED` is optional.

   Defaults to 100,000 GET requests and 20 concurrent workers. Concurrency is configurable
   from 1 to 20; smaller request counts are supported for smoke tests. Connections are
   reused, and only the configured number of workers is created. Requests use an evenly
   distributed, shuffled pool of installation IDs: with the defaults, each of 1000 IDs
   appears exactly 100 times. If there are fewer requests than installations, the pool
   shrinks to the request count. Each run generates a new ID pool; `--random-seed` repeats
   both IDs and request data independently of concurrency and response order.

   Each request randomizes `current_version` (2023.1.1–2026.9.2), `is_corporate`,
   `is_internal`, `offset`, and `limit`, plus User-Agent, Accept-Language, and optional
   Referer headers. Generated query parameters replace matching parameters in the URL;
   other query parameters are preserved. The IP is randomized within documentation-only
   ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) and sent consistently in
   `X-Forwarded-For`, `X-Real-IP`, and `Forwarded`. Referers use synthetic `.example.test`
   hosts. These headers do not change the actual network source address. Analytics reads
   `request.client.host`, so recording the synthetic IP requires Uvicorn proxy headers
   and trust for the load generator's connection source (`--forwarded-allow-ips`). The
   Docker entrypoint already configures this; other server launch methods may need it.

   Progress is printed every 5,000 requests (`--progress-every 0`
   disables it). The final summary includes throughput, HTTP statuses, and transport
   errors; any non-2xx response or transport error gives a nonzero exit code. The request
   count means attempts; failures are counted and are not retried. Redirects are not
   followed, so use the trailing slash. Analytics rows depend on the server's
   `FLAG_API_ANALYTICS_ENABLED` setting and successful ClickHouse background inserts;
   100,000 HTTP attempts do not guarantee 100,000 analytics rows.

   Both commands can also run as standalone modules: `src.modules.cli.seed_releases`
   and `src.modules.cli.load_test`. The standalone load test needs no database or app secrets.

## Swagger Documentation

When enabled, the Swagger documentation is available at `/docs` and ReDoc at `/redoc`.

## Environment Variables

| Variable                      | Type   |     Default | Required | Description                                        |
|-------------------------------|--------|------------:|:--------:|----------------------------------------------------|
| APP_SECRET_KEY                | string |           - |   yes    | Secret key                                         |
| APP_HOST                      | string |   localhost |          | Host address for the application                   |
| APP_PORT                      | int    |        8004 |          | Port for the application                           |
| JWT_ALGORITHM                 | string |       HS256 |          | JWT algorithm                                      |
| UT_TIMEZONE                   | string |        None |          | UI timezone (e.g. 'Europe/Moscow')                 |

### Admin Settings (AdminSettings, env prefix `ADMIN_`)

| Variable                      | Type   |            Default | Required | Description                             |
|-------------------------------|--------|-------------------:|:--------:|-----------------------------------------|
| ADMIN_USERNAME                | string |              admin |          | Default admin username                  |
| ADMIN_PASSWORD                | string |     release-admin! |          | Default (initial) admin password        |
| ADMIN_SESSION_EXPIRATION_TIME | int    |             172800 |          | Admin session expiration time (seconds) |
| ADMIN_BASE_URL                | string |              /radm |          | Admin panel base URL                    |
| ADMIN_TITLE                   | string |      Release Agent |          | Admin panel title                       |

### Logging Settings (LogSettings, env prefix `LOG_`)

| Variable               | Type   |                                                           Default | Required | Description                                      |
|------------------------|--------|------------------------------------------------------------------:|:--------:|--------------------------------------------------|
| LOG_LEVEL              | string |                                                              INFO |          | One of DEBUG / INFO / WARNING / ERROR / CRITICAL |
| LOG_SKIP_STATIC_ACCESS | bool   |                                                             false |          | Skip logging access to static files              |
| LOG_FORMAT             | string | [%(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s |          | Log message format                               |
| LOG_DATEFMT            | string |                                                 %d.%m.%Y %H:%M:%S |          | Date format for log timestamps                   |

### Feature Flags (FlagsSettings, env prefix `FLAG_`)

| Variable               | Type | Default | Required | Description                         |
|------------------------|------|--------:|:--------:|-------------------------------------|
| FLAG_OFFLINE_MODE      | bool |   false |          | Enable offline mode                 |
| FLAG_DEBUG_MODE        | bool |   false |          | Enable debug mode                   |
| FLAG_API_DOCS_ENABLED  | bool |   false |          | Enable FastAPI docs (Swagger/ReDoc) |
| FLAG_API_CACHE_ENABLED | bool |    true |          | Enable API response caching         |
| FLAG_USE_REDIS         | bool |    true |          | Enable Redis cache backend          |

### Database (DBSettings, env prefix `DB_`)

| Variable         | Type   |            Default | Required | Description       |
|------------------|--------|-------------------:|:--------:|-------------------|
| DB_DRIVER        | string | postgresql+asyncpg |          | SQLAlchemy driver |
| DB_HOST          | string |          localhost |          | Database host     |
| DB_PORT          | int    |               5432 |          | Database port     |
| DB_USER          | string |           postgres |          | Database username |
| DB_PASSWORD      | string |           postgres |          | Database password |
| DB_NAME          | string |      release_agent |          | Database name     |
| DB_POOL_MIN_SIZE | int    |                  - |          | Pool min size     |
| DB_POOL_MAX_SIZE | int    |                  - |          | Pool max size     |
| DB_ECHO          | bool   |              false |          | SQLAlchemy echo   |

### Redis Settings (RedisSettings, env prefix `REDIS_`)

| Variable                     | Type   |   Default | Required | Description                            |
|------------------------------|--------|----------:|:--------:|----------------------------------------|
| REDIS_HOST                   | string | localhost |          | Redis host                             |
| REDIS_PORT                   | int    |      6379 |          | Redis port                             |
| REDIS_DB                     | int    |         0 |          | Redis database number                  |
| REDIS_SOCKET_CONNECT_TIMEOUT | int    |         5 |          | Socket connection timeout (seconds)    |
| REDIS_SOCKET_TIMEOUT         | int    |         5 |          | Socket timeout (seconds)               |
| REDIS_DECODE_RESPONSES       | bool   |      true |          | Decode responses from bytes to strings |
| REDIS_MAX_CONNECTIONS        | int    |         5 |          | Maximum number of connections in pool  |

### ClickHouse Settings (ClickHouseSettings, env prefix `CH_`)

| Variable         | Type   |    Default | Required | Description                                 |
|------------------|--------|-----------:|:--------:|---------------------------------------------|
| CH_HOST          | string |  localhost |          | ClickHouse host                             |
| CH_PORT          | int    |       8123 |          | ClickHouse HTTP port                        |
| CH_USER          | string |   releases |          | ClickHouse username                         |
| CH_PASSWORD      | string |          - |   yes    | ClickHouse password                         |
| CH_DATABASE      | string |   releases |          | ClickHouse database name                    |
| CH_SECURE        | bool   |      false |          | Use HTTPS connection                        |
| CH_TIMEOUT       | int    |         10 |          | Connection timeout (seconds)                |
| CH_IGNORE_DOMAIN | string | domain.com |          | Domain excluded from analytics stat queries |

### Analytics

The application automatically logs all requests to the `/public/releases` endpoint to ClickHouse for analytics purposes.

**Logged Data:**
- Request timestamp
- Client version (optional query parameter)
- Installation ID (optional query parameter)
- Corporate client flag (optional query parameter)
- Requested product name
- Request path and method
- HTTP response status
- Response time (milliseconds)
- Client IP address
- User-Agent header

**API Endpoint:**
```
GET /public/releases?product=podcasts&offset=0&limit=10&client_version=1.0.0&installation_id=abc123&is_corporate=true
```

**Query Parameters:**
- `offset` - Number of items to skip (default: 0)
- `limit` - Maximum number of items to return (default: 10, max: 100)
- `product` - Optional product name whose releases to return. When omitted, the product marked as default is used; if no product is marked and exactly one exists, that product is used automatically.
- `client_version` - Client version string (optional)
- `installation_id` - Installation ID (optional)
- `is_corporate` - Whether client is corporate (optional, boolean)

Analytics logging is performed asynchronously and does not block the API response. If ClickHouse is unavailable, the application will continue to function normally, but analytics data will not be logged.

### Container / Infra

| Variable     | Type   | Default |       Required       | Description                                                                 |
|--------------|--------|--------:|:--------------------:|-----------------------------------------------------------------------------|
| APP_SERVICE  | string |       - |   yes (container)    | Selects entrypoint behavior: `web` / `test` / `lint`                        | 
| DOCKER_IMAGE | string |       - | yes (docker-compose) | Image tag used by `docker-compose.yml`                                      |
| APP_PORT     | int    |       - | yes (docker-compose) | Port mapping for `docker-compose.yml` (should match application `APP_PORT`) |
