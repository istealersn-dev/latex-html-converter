# Docker Setup Guide

## Overview

The LaTeX to HTML5 Converter is designed to run entirely in Docker. The application consists of:
- **Backend**: FastAPI application (Python)
- **Frontend**: Integrated single-page application served by FastAPI at `/`

Both frontend and backend run in the same Docker container.

---

## Quick Start

### 1. Build and Start the Development Environment

```bash
# Build the Docker image (first time only, or after dependency changes)
./scripts/docker-dev.sh build

# Start the development server with hot-reload
./scripts/docker-dev.sh start
```

### 2. Access the Application

- **Web UI**: http://localhost:8000
- **API Health Check**: http://localhost:8000/api/v1/health
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:8000/redoc

### 3. Verify It's Running

```bash
# Check container status
./scripts/docker-dev.sh status

# Check service health
./scripts/docker-dev.sh health

# View logs
./scripts/docker-dev.sh logs
```

---

## Docker Architecture

### Container Structure

```
latex-html-converter (Container)
├── FastAPI Backend (Port 8000)
│   ├── API Endpoints (/api/v1/*)
│   ├── Web UI (/) - Serves index.html
│   └── Static Files (/static/*)
└── LaTeX Tools
    ├── TeXLive (texlive-full)
    ├── LaTeXML
    ├── dvisvgm
    └── poppler-utils
```

### Volume Mounts (Development)

- **Source Code**: `.:/app` - Hot-reload enabled
- **Uploads**: `./.sample/uploads:/app/uploads`
- **Outputs**: `./.sample/outputs:/app/outputs`
- **Logs**: `./.sample/logs:/app/logs`

---

## Development Workflow

### Starting the Server

```bash
# Option 1: Using helper script (recommended)
./scripts/docker-dev.sh start

# Option 2: Using docker-compose directly
docker-compose up -d

# Option 3: With logs visible (foreground)
docker-compose up
```

### Hot Reload

The development setup includes hot-reload:
- **Backend**: Uvicorn with `--reload` flag
- **Frontend**: Changes to `app/templates/index.html` are reflected immediately
- **Python Code**: Changes trigger automatic server restart

### Viewing Logs

```bash
# Follow logs in real-time
./scripts/docker-dev.sh logs

# Or using docker-compose
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100
```

### Accessing Container Shell

```bash
# Open bash shell in running container
./scripts/docker-dev.sh shell

# Or using docker-compose
docker-compose exec latex-converter /bin/bash
```

### Running Tests

```bash
# Run tests inside container
./scripts/docker-dev.sh test

# Or manually
docker-compose exec latex-converter poetry run pytest
```

### Stopping the Server

```bash
# Stop containers
./scripts/docker-dev.sh stop

# Or using docker-compose
docker-compose down
```

---

## Docker Configuration Files

### docker-compose.yml (Development)

- **Service**: `latex-converter`
- **Port**: `8000:8000`
- **Hot Reload**: Enabled (`--reload` flag)
- **Volumes**: Source code mounted for live editing
- **Environment**: Development settings

### Dockerfile

- **Base Image**: `texlive/texlive:latest`
- **Python**: 3.11+ (from TeXLive image)
- **Dependencies**: Installed via Poetry
- **User**: Runs as `appuser` (non-root)
- **Health Check**: Built-in health endpoint

### Key Features

1. **TeXLive Integration**: Full LaTeX distribution included
2. **Poetry**: Dependency management
3. **Hot Reload**: Automatic code reloading in development
4. **Volume Mounts**: Persistent data and live code editing
5. **Health Checks**: Automatic container health monitoring

---

## Environment Variables

### Development (docker-compose.yml)

```yaml
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
HOST=0.0.0.0
PORT=8000
TECTONIC_PATH=/usr/local/bin/tectonic
LATEXML_PATH=/usr/bin/latexmlc
DVISVGM_PATH=/usr/bin/dvisvgm
```

### Customization

Create a `.env` file (based on `docker.env.template`) to override settings:

```bash
cp docker.env.template .env
# Edit .env with your settings
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
./scripts/docker-dev.sh logs

# Check container status
docker ps -a | grep latex-html-converter

# Rebuild from scratch
./scripts/docker-dev.sh clean
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start
```

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Stop existing containers
docker-compose down

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Health Check Failing

```bash
# Check if service is responding
curl http://localhost:8000/api/v1/health

# Check container logs
./scripts/docker-dev.sh logs

# Restart container
./scripts/docker-dev.sh restart
```

### Dependencies Not Updating

```bash
# Rebuild image (no cache)
./scripts/docker-dev.sh clean
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start
```

---

## Production Setup

For production, use `docker-compose.prod.yml`:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Differences from Development:**
- No hot-reload
- Optimized build
- Production environment variables
- Resource limits
- No source code volume mounts

---

## Helper Script Commands

```bash
./scripts/docker-dev.sh build      # Build Docker image
./scripts/docker-dev.sh start     # Start development environment
./scripts/docker-dev.sh stop      # Stop containers
./scripts/docker-dev.sh restart   # Restart environment
./scripts/docker-dev.sh logs      # Show container logs
./scripts/docker-dev.sh shell     # Open shell in container
./scripts/docker-dev.sh test      # Run tests
./scripts/docker-dev.sh clean     # Clean up everything
./scripts/docker-dev.sh status    # Show container status
./scripts/docker-dev.sh health    # Check service health
./scripts/docker-dev.sh help      # Show help message
```

---

## Notes

1. **First Build**: The initial build may take 10-15 minutes due to TeXLive installation
2. **Image Size**: The Docker image is large (~4GB) due to TeXLive
3. **Hot Reload**: Only works in development mode (docker-compose.yml)
4. **Frontend**: The frontend is integrated - no separate frontend server needed
5. **Port**: Default port is 8000, change in docker-compose.yml if needed

---

## Next Steps

After starting the Docker environment:

1. **Access Web UI**: Open http://localhost:8000 in your browser
2. **Test API**: Visit http://localhost:8000/docs for interactive API documentation
3. **Submit Conversion**: Use the web UI or API to convert LaTeX files
4. **Monitor Logs**: Use `./scripts/docker-dev.sh logs` to see real-time activity
