# Release Agent Application

Small helper for configurable release versions

## Prerequisites

- Docker and Docker Compose
- Python 3.13 (for local development)
- uv package manager

## Service Installation

### Upload config files
```shell
TARGET_SERVER="remote-server-ip"
TARGET_DIR="/opt/release-agent"
ssh ${TARGET_SERVER} -C  "mkdir -P ${TARGET_DIR}"
scp -r etc/* ${TARGET_SERVER}:${TARGET_DIR}
```

### Prepare service
```shell
ssh ${TARGET_SERVER}

# on the remote server
sudo su

export TARGET_SERVER="remote-server-ip"
export TARGET_DIR="/opt/release-agent"

# prepare user and group (NOTE: ID 1005 is imported ID for group)
groupadd --system release-agent-srv --gid 1007
useradd --no-log-init --system --gid release-agent-srv --uid 1007 release-agent-srv

chown release-agent-srv:release-agent-srv -R /opt/release-agent/
usermod -a -G docker release-agent-srv
chmod -R 660 /opt/release-agent # all files can be rewritable by release-agent-srv group
chmod -R ug+x /opt/release-agent/bin # release-agent-srv group can execute bin files (for service running)
chmod ug+x /opt/release-agent # release-agent-srv group can execute bin files (for service running)

# copy config to systemd
ln -s ${TARGET_DIR}/release-agent.service /etc/systemd/system/release-agent.service
systemctl daemon-reload
systemctl enable release-agent.service
systemctl start release-agent.service

# see status and logs
systemctl status release-agent.service
journalctl -u release-agent
```
### Prepare for deployment
1. Prepare "deploy" user
2. Allow access to service's group (to make changes in specific directories)
   ```shell
   usermod -a -G release-agent-srv deploy
   ```
3. Allow "deploy" user manipulate with release-agent's service
   ```shell
   visudo -f /etc/sudoers.d/deploy
   # add these lines:
   deploy ALL = NOPASSWD: /bin/systemctl restart release-agent.service
   deploy ALL = NOPASSWD: /bin/systemctl show -p ActiveState --value release-agent
   ```

## Service Management

The application includes a convenient service management script located at `bin/service` on the server. This script provides easy access to common service operations.

### Using the Service Script

```bash
# Basic commands
bin/service start          # Start the service
bin/service stop           # Stop the service  
bin/service restart        # Restart the service
bin/service status         # Show service status
bin/service health         # Check service health

# View logs
bin/service logs                    # Show recent logs (last 50 lines)
bin/service logs --tail 100         # Show last 100 lines
bin/service logs --follow           # Follow logs in real-time
bin/service logs --grep error       # Filter logs by pattern
bin/service logs --since "1 hour ago"  # Show logs since specific time

# Start/restart with log following
bin/service start --logs            # Start and follow logs
bin/service restart --logs          # Restart and follow logs
```

### Service Script Features

- **Health checks**: Verify service status and check for recent errors
- **Flexible logging**: Filter logs by time, pattern, or follow in real-time
- **Easy management**: Simple commands for start/stop/restart operations
- **Error detection**: Automatic detection of service issues

### Nginx Configuration

The service requires Nginx as a reverse proxy to handle:
- Domain-based routing (release.example.com)
- Security layer (authorization header check)
- API endpoint protection (only /api/* endpoints are accessible)

**Important**: The application runs in a container via uvicorn with specific flags for proper reverse proxy interaction:
- `--proxy-headers`: Enables processing of proxy headers (X-Forwarded-For, X-Forwarded-Proto, etc.)
- `--forwarded-allow-ips`: Allows trusted proxy IPs to set forwarded headers

These flags are essential for correct client IP detection and protocol handling when behind Nginx.

To configure Nginx:

1. Copy the configuration file from `etc/nginx.conf` to your Nginx configuration directory:
   ```bash
   sudo cp etc/nginx.conf /etc/nginx/sites-available/release-agent.conf
   ```

2. Create a symbolic link to enable the site:
   ```bash
   sudo ln -s /etc/nginx/sites-available/release-agent.conf /etc/nginx/sites-enabled/
   ```

3. Update the configuration:
   - Replace `release-agent.example.com` with your domain
   - Update the port in `proxy_pass` directive to match your application port
   - Ensure the `Authorization` header is properly set in all API requests

4. Test and reload Nginx:
   ```bash
   sudo nginx -t
   sudo nginx -s reload
   ```

5. Set up HTTPS with Certbot (recommended):
   ```bash
   # Install Certbot and Nginx plugin
   sudo apt update
   sudo apt install certbot python3-certbot-nginx
   
   # Obtain and install SSL certificate
   sudo certbot --nginx -d release.example.com
   
   # Verify auto-renewal is enabled
   sudo systemctl status certbot.timer
   ```

After running Certbot, it will:
- Automatically modify your Nginx configuration to handle HTTPS
- Set up automatic certificate renewal (every 90 days)
- Configure secure SSL settings
- Optionally redirect all HTTP traffic to HTTPS (recommended)

Note: Make sure your domain's DNS records are properly configured and pointing to your server before running Certbot.

## Development

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

### Environment Variables

| Variable                      | Type   |     Default | Required | Description                                        |
|-------------------------------|--------|------------:|:--------:|----------------------------------------------------|
| API_DOCS_ENABLED              | bool   |       false |          | Enable FastAPI docs (Swagger/ReDoc)                |
| APP_SECRET_KEY                | string |           - |   yes    | Secret key                                         |
| APP_HOST                      | string |   localhost |          | Host address for the application                   |
| APP_PORT                      | int    |        8003 |          | Port for the application                           |
| JWT_ALGORITHM                 | string |       HS256 |          | JWT algorithm                                      |

### Admin Settings (AdminSettings, env prefix `ADMIN_`)

| Variable                      | Type   |         Default | Required | Description                             |
|-------------------------------|--------|----------------:|:--------:|-----------------------------------------|
| ADMIN_USERNAME                | string |           admin |          | Default admin username                  |
| ADMIN_PASSWORD                | string |     release-admin! |          | Default (initial) admin password        |
| ADMIN_SESSION_EXPIRATION_TIME | int    |          172800 |          | Admin session expiration time (seconds) |
| ADMIN_BASE_URL                | string |           /radm |          | Admin panel base URL                    |
| ADMIN_TITLE                   | string | releaseAgent Admin |          | Admin panel title                       |

### Logging Settings (LogSettings, env prefix `LOG_`)

| Variable               | Type   |                                                           Default | Required | Description                                      |
|------------------------|--------|------------------------------------------------------------------:|:--------:|--------------------------------------------------|
| LOG_LEVEL              | string |                                                              INFO |          | One of DEBUG / INFO / WARNING / ERROR / CRITICAL |
| LOG_SKIP_STATIC_ACCESS | bool   |                                                             false |          | Skip logging access to static files              |
| LOG_FORMAT             | string | [%(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s |          | Log message format                               |
| LOG_DATEFMT            | string |                                                 %d.%m.%Y %H:%M:%S |          | Date format for log timestamps                   |

### Feature Flags (FlagsSettings, env prefix `FLAG_`)

| Variable          | Type | Default | Required | Description         |
|-------------------|------|--------:|:--------:|---------------------|
| FLAG_OFFLINE_MODE | bool |   false |          | Enable offline mode |

### Database (DBSettings, env prefix `DB_`)

| Variable         | Type   |            Default | Required | Description       |
|------------------|--------|-------------------:|:--------:|-------------------|
| DB_DRIVER        | string | postgresql+asyncpg |          | SQLAlchemy driver |
| DB_HOST          | string |          localhost |          | Database host     |
| DB_PORT          | int    |               5432 |          | Database port     |
| DB_USERNAME      | string |           postgres |          | Database username |
| DB_PASSWORD      | string |           postgres |          | Database password |
| DB_DATABASE      | string |         release_agent |          | Database name     |
| DB_POOL_MIN_SIZE | int    |                  - |          | Pool min size     |
| DB_POOL_MAX_SIZE | int    |                  - |          | Pool max size     |
| DB_ECHO          | bool   |              false |          | SQLAlchemy echo   |

### CLI utilities

These are used by `src/cli/simple_ai_client.py`.

| Variable           | Type   | Default | Required | Description                                                             |
|--------------------|--------|--------:|:--------:|-------------------------------------------------------------------------|
| CLI_AI_API_TOKEN   | string |       - |   yes*   | Authorization token for the CLI (required unless `--token` is provided) |
| CLI_AI_TEMPERATURE | float  |     0.7 |          | Sampling temperature                                                    |
| CLI_AI_MAX_TOKENS  | int    |    1000 |          | Max tokens in completion                                                |
| CLI_AI_TIMEOUT     | int    |    3600 |          | HTTP timeout (seconds)                                                  |

### Container / Infra

| Variable     | Type   | Default |       Required       | Description                                                                 |
|--------------|--------|--------:|:--------------------:|-----------------------------------------------------------------------------|
| APP_SERVICE  | string |       - |   yes (container)    | Selects entrypoint behavior: `web` / `test` / `lint`                        | 
| DOCKER_IMAGE | string |       - | yes (docker-compose) | Image tag used by `docker-compose.yml`                                      |
| APP_PORT     | int    |       - | yes (docker-compose) | Port mapping for `docker-compose.yml` (should match application `APP_PORT`) |
