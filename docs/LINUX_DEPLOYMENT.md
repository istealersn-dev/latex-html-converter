# Linux Deployment Guide

This guide covers the ideal ways to deploy the LaTeX to HTML5 Converter on Linux systems.

## 🐳 Option 1: Docker (Recommended)

**Best for**: Production, development, and consistent deployments

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+ (optional but recommended)

### Quick Start

```bash
# Build and start
docker-compose up -d

# Or using the helper script
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start

# Check status
docker-compose ps
curl http://localhost:8000/api/v1/health
```

### Production Deployment

```bash
# Build production image
docker build -t latex-html-converter:latest .

# Run with production settings
docker run -d \
  --name latex-converter \
  -p 8000:8000 \
  -v /var/lib/latex-converter/uploads:/app/uploads \
  -v /var/lib/latex-converter/outputs:/app/outputs \
  -v /var/lib/latex-converter/logs:/app/logs \
  -e ENVIRONMENT=production \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  latex-html-converter:latest
```

### Advantages
- ✅ All dependencies pre-installed (TeXLive, LaTeXML, Python packages)
- ✅ Consistent environment across different Linux distributions
- ✅ Easy updates and rollbacks
- ✅ Isolated from host system
- ✅ Built-in health checks

---

## 🔧 Option 2: Systemd Service with Poetry

**Best for**: Native Linux deployment, maximum performance, system integration

### Prerequisites
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    python3.11+ \
    python3-pip \
    python3-venv \
    texlive-full \
    texlive-latex-extra \
    texlive-science \
    texlive-publishers \
    latexml \
    dvisvgm \
    curl \
    git

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

### Setup Steps

1. **Clone and install dependencies**
```bash
cd /opt
sudo git clone <repository-url> latex-html-converter
cd latex-html-converter
sudo poetry install --no-dev
```

2. **Create systemd service file**
```bash
sudo nano /etc/systemd/system/latex-converter.service
```

3. **Service file content** (`/etc/systemd/system/latex-converter.service`):
```ini
[Unit]
Description=LaTeX to HTML5 Converter Service
After=network.target

[Service]
Type=simple
User=latex-converter
Group=latex-converter
WorkingDirectory=/opt/latex-html-converter
Environment="PATH=/opt/latex-html-converter/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="ENVIRONMENT=production"
Environment="DEBUG=false"
Environment="LOG_LEVEL=INFO"
Environment="HOST=0.0.0.0"
Environment="PORT=8000"
ExecStart=/opt/latex-html-converter/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/latex-html-converter/uploads /opt/latex-html-converter/outputs /opt/latex-html-converter/logs

[Install]
WantedBy=multi-user.target
```

4. **Create user and directories**
```bash
sudo useradd -r -s /bin/false latex-converter
sudo mkdir -p /opt/latex-html-converter/{uploads,outputs,logs}
sudo chown -R latex-converter:latex-converter /opt/latex-html-converter
```

5. **Enable and start service**
```bash
sudo systemctl daemon-reload
sudo systemctl enable latex-converter
sudo systemctl start latex-converter
sudo systemctl status latex-converter
```

### Advantages
- ✅ Native performance (no container overhead)
- ✅ System integration (systemd, logging, monitoring)
- ✅ Better resource utilization
- ✅ Direct access to system tools

---

## 📦 Option 3: Native Installation with Virtual Environment

**Best for**: Development, testing, single-server deployments

### Setup

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3.11+ \
    python3-pip \
    python3-venv \
    texlive-full \
    texlive-latex-extra \
    texlive-science \
    latexml \
    dvisvgm

# Clone repository
git clone <repository-url>
cd latex-html-converter

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install poetry
poetry install

# Start service
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run as background service (using screen/tmux)

```bash
# Using screen
screen -S latex-converter
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+A then D to detach

# Using tmux
tmux new -s latex-converter
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+B then D to detach
```

---

## 🔒 Option 4: Production with Reverse Proxy (Nginx)

**Best for**: Production deployments with SSL, load balancing, static file serving

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/latex-converter
upstream latex_converter {
    server 127.0.0.1:8000;
    # Add more servers for load balancing
    # server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # File upload size limit
    client_max_body_size 100M;
    
    # Proxy settings
    location / {
        proxy_pass http://latex_converter;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
    
    # Serve static files directly (if any)
    location /static/ {
        alias /opt/latex-html-converter/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Setup SSL with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 📊 Monitoring and Logging

### Systemd Journal

```bash
# View logs
sudo journalctl -u latex-converter -f

# View last 100 lines
sudo journalctl -u latex-converter -n 100

# View logs since today
sudo journalctl -u latex-converter --since today
```

### Application Logs

Logs are written to `/opt/latex-html-converter/logs/` (or configured path).

### Health Monitoring

```bash
# Simple health check script
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health)
if [ $response -eq 200 ]; then
    echo "Service is healthy"
else
    echo "Service is unhealthy (HTTP $response)"
    # Restart service
    sudo systemctl restart latex-converter
fi
```

---

## 🔄 Updates and Maintenance

### Docker Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Systemd Service Updates

```bash
# Pull latest code
cd /opt/latex-html-converter
sudo git pull

# Update dependencies
sudo poetry install --no-dev

# Restart service
sudo systemctl restart latex-converter
```

---

## 🎯 Recommendation Matrix

| Use Case | Recommended Option | Why |
|----------|-------------------|-----|
| **Production** | Docker + Nginx | Isolation, easy updates, SSL support |
| **Development** | Docker Compose | Hot-reload, easy setup |
| **High Performance** | Systemd Service | Native performance, system integration |
| **Quick Testing** | Virtual Environment | Fast setup, no system changes |
| **Multi-server** | Docker Swarm/Kubernetes | Orchestration, scaling |

---

## 🚀 Quick Start Commands

### Docker (Production)
```bash
docker-compose -f docker-compose.yml up -d
```

### Systemd
```bash
sudo systemctl start latex-converter
sudo systemctl enable latex-converter
```

### Direct
```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 📝 Notes

- **TeXLive**: The Dockerfile installs `texlive-full` which is large (~5GB). For production, consider using a smaller TeXLive distribution and installing packages on-demand.
- **Package Management**: The service automatically tries to install missing LaTeX packages using `tlmgr` (available in Docker) or `apt-get` (on native Linux).
- **Resource Requirements**: 
  - Minimum: 2GB RAM, 2 CPU cores
  - Recommended: 4GB+ RAM, 4+ CPU cores
  - Disk: 10GB+ for TeXLive installation

