# Installation Guide

## Server Requirements

- **OS**: Ubuntu/Debian
- **Docker**: Docker and Docker Compose installed
- **RAM**: 512 MB minimum
- **CPU**: 1 CPU core minimum

## Service Installation

### Prepare service
```shell
ssh ${TARGET_SERVER}

# on the remote server
sudo su

export TARGET_SERVER="remote-server-ip"
export TARGET_DIR="/opt/release-agent"

# prepare user and group (NOTE: ID 1005 is imported ID for group)
groupadd --system release-agent-srv --gid 1008
useradd --no-log-init --system --gid release-agent-srv --uid 1008 release-agent-srv

mkdir -p $TARGET_DIR/bin
chown release-agent-srv:release-agent-srv -R ${TARGET_DIR}
usermod -a -G docker release-agent-srv
chown release-agent-srv:release-agent-srv -r ${TARGET_DIR} 
chmod -R 660 ${TARGET_DIR} # all files can be rewritable by release-agent-srv group
chmod -R ug+x ${TARGET_DIR}/bin # release-agent-srv group can execute bin files (for service running)
chmod ug+x ${TARGET_DIR} # release-agent-srv group can execute bin files (for service running)

# make env-file
cp ${TARGET_DIR}/.env.template ${TARGET_DIR}/.env
chown release-agent-srv:root ${TARGET_DIR}/.env
# change required params here:
nano ${TARGET_DIR}/.env
# only read access from service
chmod 400 ${TARGET_DIR}/.env

# copy config to systemd
ln -s ${TARGET_DIR}/release-agent.service /etc/systemd/system/release-agent.service
systemctl daemon-reload
systemctl enable release-agent.service
systemctl start release-agent.service

# see status and logs
systemctl status release-agent.service
journalctl -u release-agent
```

### Setup for deployment

Note: we assume that deployment actions will be performed as the `deploy` SSH user

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

### Nginx Configuration as a Reverse Proxy

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
   sudo cp nginx.conf /etc/nginx/sites-available/release-agent.conf
   ```

2. Create a symbolic link to enable the site:
   ```bash
   sudo ln -s /etc/nginx/sites-available/release-agent.conf /etc/nginx/sites-enabled/
   ```

3. Update the configuration:
   ```bash
   sudo nano /etc/nginx/sites-available/release-agent.conf
   ```
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
   sudo certbot --nginx -d releases.example.com
   
   # Verify auto-renewal is enabled
   sudo systemctl status certbot.timer
   ```

After running Certbot, it will:
- Automatically modify your Nginx configuration to handle HTTPS
- Set up automatic certificate renewal (every 90 days)
- Configure secure SSL settings
- Optionally redirect all HTTP traffic to HTTPS (recommended)

Note: Make sure your domain's DNS records are properly configured and pointing to your server before running Certbot.

