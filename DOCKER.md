# Dockerize LaTeX to HTML5 Converter

## Overview

Transition the entire application to Docker using the official TeXLive image for both local development and AWS ECS Fargate production deployment.

## Implementation Steps

### 1. Create DOCKER.md Documentation

Create `DOCKER.md` with comprehensive Docker documentation:

- Architecture overview and design decisions
- Local development setup instructions
- Production deployment guidelines for AWS ECS Fargate
- Troubleshooting common issues
- Tool paths and configuration reference
- Complete implementation plan and rationale

### 2. Create Dockerfile

Create `Dockerfile` with proper multi-stage configuration:

- Use `texlive/texlive:latest` as base image (~4GB)
- Install Python 3.11+ and system dependencies
- Install Poetry for dependency management
- Copy application code and install Python dependencies
- Configure proper working directory and expose port 8000
- Set appropriate user permissions

### 3. Create Docker Compose Configuration

Create `docker-compose.yml` for local development:

- Define service for the converter application
- Mount source code as volume for hot-reloading
- Map port 8000 to host
- Set environment variables for development mode
- Configure persistent volumes for uploads/outputs
- Enable interactive terminal for debugging

### 4. Create .dockerignore

Create `.dockerignore` to optimize build:

- Python cache files (`__pycache__`, `*.pyc`, `*.pyo`)
- Virtual environments (`venv/`, `.venv/`, `env/`)
- Poetry cache and lock files
- Git directory (`.git/`)
- Test files, coverage reports, and pytest cache
- Local uploads/outputs directories
- IDE configurations (`.vscode/`, `.idea/`)

### 5. Update Configuration for Docker

Modify `app/config.py`:

- Change tool paths from macOS Homebrew paths to Docker Linux paths
- Make all paths configurable via environment variables with Field()
- Set Docker-appropriate defaults:
- `TECTONIC_PATH: str` → `/usr/local/bin/tectonic` (or check actual TeXLive path)
- `LATEXML_PATH: str` → `/usr/bin/latexml` (or TeXLive bin path)
- `DVISVGM_PATH: str` → `/usr/bin/dvisvgm` (or TeXLive bin path)

### 6. Create Docker Environment Template

Create `.env.docker` template file:

- Document all available environment variables
- Provide sensible defaults for Docker environment
- Include tool paths, timeouts, resource limits
- Add comments explaining each variable's purpose

### 7. Create Development Helper Script

Create `scripts/docker-dev.sh`:

- Commands to build Docker image
- Start development environment with hot-reload
- View logs and container status
- Stop and clean up containers
- Run tests inside container

### 8. Update Main README

Update `README.md` with Docker section:

- Add "Docker Setup" section early in the document
- Link to DOCKER.md for detailed instructions
- Provide quick-start Docker commands
- Note that Docker is now the recommended way to run the application

### 9. Test Docker Setup

Comprehensive testing:

- Build Docker image successfully
- Run container and verify startup
- Test health endpoint
- Test conversion with simple LaTeX file
- Verify all tools (Tectonic, LaTeXML, dvisvgm) are accessible
- Test volume mounts for persistence
- Verify hot-reload works in development

## Key Files to Create/Modify

**New Files:**

- `DOCKER.md` - Comprehensive Docker documentation and plan
- `Dockerfile` - Main Docker image definition
- `docker-compose.yml` - Local development orchestration
- `.dockerignore` - Build optimization
- `.env.docker` - Environment variables template
- `scripts/docker-dev.sh` - Development helper script

**Modified Files:**

- `app/config.py` - Update tool paths for Docker environment
- `README.md` - Add Docker quick-start section

## Technical Considerations

1. **Image Size**: Official TeXLive image (~4GB) is acceptable for production servers and AWS Fargate
2. **Tool Paths**: Need to verify actual paths in TeXLive Docker image (may differ from standard Linux paths)
3. **Hot Reload**: Use volume mounts in docker-compose for instant code changes
4. **Persistence**: Separate volumes for uploads and outputs to survive container restarts
5. **AWS ECS Fargate**: Single Dockerfile works for both local and cloud deployment
6. **Environment Configuration**: All settings overridable via environment variables
7. **Port Mapping**: Default 8000, but configurable for different environments