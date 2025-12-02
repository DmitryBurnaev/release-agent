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
   # Usage: python -m src.modules.cli.management [OPTIONS]
   # Change the admin password.   
   # Options:
   #   --help                           Show this help message
   #   --username TEXT                  Admin username
   #   --random-password                Generate a random password.
   #   --random-password-length INTEGER Set length of generated random password.

   # Example: change password for admin to auto-generated password with length 32 symbols
   uv run python -m src.modules.cli.management --username admin --random-password --random-password-length 32

   # Example: change password for my-user to password from stdin
   uv run python -m src.modules.cli.management --username my-user
   # ===
   # Changing admin password...
   # Set a new password for my-user
   # New Password: <INPUT>
   # Repeat for confirmation: <INPUT>
   ```


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

### Container / Infra

| Variable     | Type   | Default |       Required       | Description                                                                 |
|--------------|--------|--------:|:--------------------:|-----------------------------------------------------------------------------|
| APP_SERVICE  | string |       - |   yes (container)    | Selects entrypoint behavior: `web` / `test` / `lint`                        | 
| DOCKER_IMAGE | string |       - | yes (docker-compose) | Image tag used by `docker-compose.yml`                                      |
| APP_PORT     | int    |       - | yes (docker-compose) | Port mapping for `docker-compose.yml` (should match application `APP_PORT`) |
