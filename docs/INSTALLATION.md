# 🛠️ Installation Guide

Complete installation and setup guide for local development of the LaTeX → HTML5 Converter.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker-recommended)
- [Local Development Setup](#local-development-setup-without-docker)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [IDE Setup](#ide-setup)
- [Troubleshooting](#troubleshooting)
- [Development Workflow](#development-workflow)

---

## Prerequisites

### Required Tools

**For Docker Setup (Recommended)**:
- Docker Desktop (v20.10+)
- Docker Compose (v2.0+)
- Git (v2.30+)
- 4GB+ free disk space for TeXLive image
- 8GB+ RAM recommended

**For Local Setup (Advanced)**:
- Python 3.11+
- Poetry (1.8+)
- LaTeX distribution (TeXLive 2023+)
- LaTeXML (0.8.6+)
- System build tools (gcc, make)
- Optional: pyenv for Python version management

### System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4GB | 8GB+ |
| Disk | 5GB | 10GB+ |
| OS | macOS 11+, Ubuntu 20.04+, Windows 10+ (WSL2) | - |

---

## Quick Start (Docker - Recommended)

This is the fastest way to get up and running. Docker handles all dependencies automatically.

### 1. Clone Repository

```bash
git clone https://github.com/istealersn-dev/latex-html-converter.git
cd latex-html-converter
```

### 2. Start Development Server

```bash
# Build and start the container
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start

# Or using docker-compose directly
docker-compose up -d
```

### 3. Verify Installation

**Check Service Health:**

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "tools": {
    "pdflatex": "available",
    "latexmlc": "available",
    "dvisvgm": "available"
  }
}
```

**Access Web UI:**
Open browser to http://localhost:8000

**Test API:**

```bash
# Create test LaTeX file
echo '\documentclass{article}\begin{document}Hello World\end{document}' > test.tex
zip test.zip test.tex

# Upload for conversion
curl -X POST http://localhost:8000/api/v1/convert \
  -F "file=@test.zip" \
  -o result.json

# Check result
cat result.json
```

### 4. View Logs (Optional)

```bash
./scripts/docker-dev.sh logs

# Or follow logs in real-time
docker-compose logs -f
```

---

## Local Development Setup (Without Docker)

For developers who prefer running services natively on their machine.

### 1. Install System Dependencies

**macOS (using Homebrew):**

```bash
# Install Python 3.11+
brew install python@3.11

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install LaTeX distribution
brew install --cask mactex-no-gui

# Install LaTeXML and tools
brew install latexml dvisvgm poppler
```

**Ubuntu/Debian:**

```bash
# Install Python 3.11+
sudo apt update
sudo apt install -y python3.11 python3.11-dev python3-pip

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install LaTeX distribution and tools
sudo apt install -y \
  texlive-full \
  latexml \
  dvisvgm \
  poppler-utils \
  build-essential
```

**Verify Installations:**

```bash
python3 --version  # Should be 3.11+
poetry --version   # Should be 1.8+
pdflatex --version
latexmlc --version
dvisvgm --version
```

### 2. Install Python Dependencies

**Using Poetry (Recommended):**

```bash
# Install all dependencies
poetry install

# Or install only production dependencies
poetry install --only=main
```

**Using pip (Alternative):**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Create Required Directories

```bash
mkdir -p uploads outputs logs
chmod 755 uploads outputs logs
```

### 4. Configure Environment

Create `.env` file (optional - defaults work for most setups):

```bash
# Copy template (optional)
cp docker.env.template .env

# Edit to set local paths if different from defaults
nano .env
```

Minimal `.env` for local development:

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
HOST=0.0.0.0
PORT=8000

# Adjust these paths if your installation differs
PDFLATEX_PATH=/usr/bin/pdflatex
LATEXML_PATH=/usr/bin/latexmlc
DVISVGM_PATH=/usr/bin/dvisvgm
```

### 5. Start Development Server

**With auto-reload:**

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. Verify Installation

Test endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

---

## Environment Configuration

### Configuration Files

- `.env` - Local environment variables (gitignored)
- `docker.env.template` - Template for Docker environment
- `app/config.py` - Application configuration schema
- `app/configs/latexml.py` - LaTeXML-specific settings

### Key Environment Variables

#### Application Settings

```bash
APP_NAME="LaTeX → HTML5 Converter"
VERSION="0.1.0"
ENVIRONMENT=development          # development, staging, or production
DEBUG=true                       # Enable debug mode
LOG_LEVEL=DEBUG                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Server Configuration

```bash
HOST=0.0.0.0                    # Bind to all interfaces
PORT=8000                       # Server port
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
ALLOWED_HOSTS=localhost,127.0.0.1
```

#### File Upload Settings

```bash
MAX_FILE_SIZE=104857600         # 100MB in bytes
ALLOWED_EXTENSIONS=.zip,.tar.gz,.tar
UPLOAD_DIR=uploads              # Upload directory path
OUTPUT_DIR=outputs              # Output directory path
```

#### External Tools (Docker Paths)

```bash
PDFLATEX_PATH=/usr/bin/pdflatex
LATEXML_PATH=/usr/bin/latexmlc
DVISVGM_PATH=/usr/bin/dvisvgm
```

**For Local Development** (adjust to your installation):

```bash
# macOS Homebrew paths (example)
PDFLATEX_PATH=/Library/TeX/texbin/pdflatex
LATEXML_PATH=/opt/homebrew/bin/latexmlc
DVISVGM_PATH=/opt/homebrew/bin/dvisvgm

# Linux standard paths
PDFLATEX_PATH=/usr/bin/pdflatex
LATEXML_PATH=/usr/bin/latexmlc
DVISVGM_PATH=/usr/bin/dvisvgm
```

#### Conversion Settings

```bash
CONVERSION_TIMEOUT=300          # 5 minutes (in seconds)
MAX_CONCURRENT_CONVERSIONS=5    # Maximum parallel conversions
CONVERSION_RETENTION_HOURS=24   # How long to keep results
```

#### Asset Handling

```bash
ASSET_PATTERNS=*.jpg,*.jpeg,*.png,*.svg,*.gif,*.webp,*.pdf
TEMPLATES_DIR=app/templates
STATIC_DIR=app/static
```

### Environment-Specific Configuration

**Development (.env):**

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
MAX_CONCURRENT_CONVERSIONS=3    # Lower for local development
```

**Staging:**

```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
ALLOWED_ORIGINS=https://staging.example.com
ALLOWED_HOSTS=staging.example.com
```

**Production:**

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
ALLOWED_ORIGINS=https://example.com
ALLOWED_HOSTS=example.com
MAX_CONCURRENT_CONVERSIONS=10   # Higher for production
CONVERSION_TIMEOUT=600          # 10 minutes for complex documents
```

---

## Running the Application

### Docker Commands

**Using Helper Script:**

```bash
# Start services
./scripts/docker-dev.sh start

# Stop services
./scripts/docker-dev.sh stop

# Restart services
./scripts/docker-dev.sh restart

# Check status
./scripts/docker-dev.sh status

# View health
./scripts/docker-dev.sh health
```

**Using Docker Compose Directly:**

```bash
# Start in detached mode
docker-compose up -d

# Start with logs visible
docker-compose up

# Stop services
docker-compose down

# Rebuild and start
docker-compose up -d --build
```

**View Container Logs:**

```bash
# Using helper script
./scripts/docker-dev.sh logs

# Using docker-compose
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100
```

**Access Container Shell:**

```bash
# Using helper script
./scripts/docker-dev.sh shell

# Using docker directly
docker exec -it latex-html-converter /bin/bash
```

### Local Commands

**Start Server:**

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Start with Custom Port:**

```bash
poetry run uvicorn app.main:app --reload --port 8080
```

**Enable Debug Mode:**

```bash
DEBUG=true LOG_LEVEL=DEBUG poetry run uvicorn app.main:app --reload
```

**Run in Background:**

```bash
nohup poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

---

## Running Tests

### Docker Environment

**Run All Tests:**

```bash
# Using helper script
./scripts/docker-dev.sh test

# Using docker-compose
docker-compose exec latex-converter poetry run pytest

# Run with verbose output
docker-compose exec latex-converter poetry run pytest -v
```

**Run Specific Test File:**

```bash
docker-compose exec latex-converter poetry run pytest tests/test_latexml_service.py
```

**Run with Coverage:**

```bash
docker-compose exec latex-converter poetry run pytest --cov=app --cov-report=html
```

**Run Integration Tests Only:**

```bash
docker-compose exec latex-converter poetry run pytest tests/ -k integration
```

### Local Environment

**Using Poetry:**

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test
poetry run pytest tests/test_latexml_service.py -v
```

**Using pytest Directly:**

```bash
# Activate virtual environment first
source $(poetry env info --path)/bin/activate

# Run tests
pytest
pytest -v
pytest tests/test_latexml_service.py
```

**Watch Mode (auto-rerun on changes):**

```bash
poetry run pytest-watch
# or
poetry run ptw
```

**Generate Coverage Report:**

```bash
poetry run pytest --cov=app --cov-report=html --cov-report=term

# Open HTML coverage report
open htmlcov/index.html
```

### Test Structure

Current test coverage:
- `tests/test_tectonic_service.py` - Tectonic compilation unit tests
- `tests/test_latexml_service.py` - LaTeXML conversion unit tests
- `tests/test_html_post_processor.py` - HTML post-processing tests
- `tests/test_tectonic_integration.py` - Tectonic integration tests
- `tests/test_latexml_integration.py` - LaTeXML integration tests
- `test_asset_conversion.py` - Asset conversion tests
- `tests/run_tests.py` - Test runner script

---

## IDE Setup

### VS Code

**Recommended Extensions:**

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Docker (ms-azuretools.vscode-docker)
- Ruff (charliermarsh.ruff)
- YAML (redhat.vscode-yaml)
- Markdown All in One (yzhang.markdown-all-in-one)

**Settings (.vscode/settings.json):**

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

**Launch Configuration (.vscode/launch.json):**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v"],
      "console": "integratedTerminal"
    }
  ]
}
```

### PyCharm

**Configuration Steps:**
1. Open project directory
2. Configure Python interpreter:
   - Settings → Project → Python Interpreter
   - Select Poetry environment or create virtual environment
3. Configure run configuration:
   - Run → Edit Configurations
   - Add Python configuration
   - Script path: `uvicorn`
   - Parameters: `app.main:app --reload --host 0.0.0.0 --port 8000`
4. Install recommended plugins:
   - Docker
   - Markdown
   - .env files support

### Code Quality Tools

**Ruff (Linter & Formatter):**

```bash
# Check code
poetry run ruff check app/

# Auto-fix issues
poetry run ruff check --fix app/

# Format code
poetry run ruff format app/
```

**MyPy (Type Checker):**

```bash
# Type check all files
poetry run mypy app/

# Type check specific file
poetry run mypy app/services/pipeline.py
```

**Pre-commit Hooks:**

```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run manually
poetry run pre-commit run --all-files

# Update hooks
poetry run pre-commit autoupdate
```

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails

**Problem:** Docker build fails with "out of space" error

**Solution:**

```bash
# Clean up Docker system
docker system prune -a
docker volume prune

# Free up space and rebuild
./scripts/docker-dev.sh clean
./scripts/docker-dev.sh build
```

#### 2. Port Already in Use

**Problem:** Error "Address already in use" on port 8000

**Solution:**

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
PORT=8080 docker-compose up -d
```

#### 3. LaTeXML Not Found

**Problem:** "latexmlc: command not found"

**Solution (Docker):**

```bash
# Rebuild Docker image to ensure LaTeXML is installed
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Solution (Local):**

```bash
# macOS
brew install latexml

# Ubuntu/Debian
sudo apt install -y latexml

# Verify installation
latexmlc --version
```

#### 4. Permission Denied Errors

**Problem:** Cannot write to uploads/outputs directories

**Solution (Docker):**

```bash
# Fix directory permissions
chmod -R 755 uploads outputs logs

# Or recreate with proper permissions
docker-compose down
rm -rf uploads outputs logs
mkdir -p uploads outputs logs
chmod 755 uploads outputs logs
docker-compose up -d
```

**Solution (Local):**

```bash
# Create directories with proper permissions
mkdir -p uploads outputs logs
chmod 755 uploads outputs logs
```

#### 5. Package Installation Fails

**Problem:** tlmgr fails to install LaTeX packages

**Solution:**

```bash
# Update tlmgr first
docker-compose exec latex-converter tlmgr update --self

# Then update all packages
docker-compose exec latex-converter tlmgr update --all

# Install specific package manually
docker-compose exec latex-converter tlmgr install <package-name>
```

#### 6. Conversion Timeouts

**Problem:** Conversions timing out after 300s

**Solution:**

```bash
# Increase timeout in .env
echo "CONVERSION_TIMEOUT=600" >> .env

# Restart services
docker-compose restart
```

#### 7. Memory Issues with Large Documents

**Problem:** Container crashes with large LaTeX projects

**Solution:**

```bash
# Increase Docker memory limit in docker-compose.yml
# Add under service:
#   deploy:
#     resources:
#       limits:
#         memory: 4G

# Or set environment variable
echo "MAX_FILE_SIZE=52428800" >> .env  # Reduce to 50MB
docker-compose restart
```

#### 8. Python Version Mismatch

**Problem:** "Python 3.11+ required" error

**Solution:**

```bash
# Install Python 3.11
# macOS
brew install python@3.11

# Ubuntu
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-dev

# Recreate virtual environment
poetry env use python3.11
poetry install
```

### Health Check Failures

**Check Service Status:**

```bash
# Docker
docker ps -a | grep latex-converter
docker-compose ps

# Check container health
docker inspect latex-html-converter | grep Health -A 10
```

**Inspect Logs:**

```bash
# View recent logs
docker-compose logs --tail=100 latex-converter

# Follow logs in real-time
docker-compose logs -f
```

**Verify Tool Availability:**

```bash
# Inside container
docker-compose exec latex-converter which pdflatex
docker-compose exec latex-converter which latexmlc
docker-compose exec latex-converter which dvisvgm

# Test each tool
docker-compose exec latex-converter pdflatex --version
docker-compose exec latex-converter latexmlc --version
docker-compose exec latex-converter dvisvgm --version
```

**Test External Tools:**

```bash
# Create simple test
echo '\documentclass{article}\begin{document}Hello\end{document}' > test.tex

# Test pdflatex
docker-compose exec latex-converter pdflatex test.tex

# Test latexmlc
docker-compose exec latex-converter latexmlc test.tex
```

### Performance Issues

**Slow Conversions:**
- Enable LaTeXML caching: `LATEXML_CACHE_BINDINGS=true`
- Increase concurrent conversions: `MAX_CONCURRENT_CONVERSIONS=10`
- Allocate more CPU/RAM to Docker

**High Memory Usage:**
- Reduce max file size: `MAX_FILE_SIZE=52428800` (50MB)
- Lower concurrent conversions: `MAX_CONCURRENT_CONVERSIONS=3`
- Enable cleanup: check `CONVERSION_RETENTION_HOURS`

### Getting Help

**Check Logs:**

```bash
# Docker logs
docker-compose logs --tail=200 latex-converter

# Local logs (if file logging enabled)
tail -f logs/app.log
```

**Report Issues:**
1. Include error logs from above commands
2. Include system info: OS, Docker version, Python version
3. Provide minimal reproduction case
4. Submit to GitHub Issues: https://github.com/istealersn-dev/latex-html-converter/issues

---

## Development Workflow

### Daily Development Cycle

**1. Start Services:**

```bash
./scripts/docker-dev.sh start
# or
poetry run uvicorn app.main:app --reload
```

**2. Make Code Changes:**
- Edit files in `app/` directory
- Changes auto-reload (Docker with `--reload` flag)
- No rebuild needed for code changes

**3. Test Changes:**

```bash
# Run tests
./scripts/docker-dev.sh test
# or
poetry run pytest -v
```

**4. View Logs:**

```bash
./scripts/docker-dev.sh logs
```

**5. Stop Services:**

```bash
./scripts/docker-dev.sh stop
# or
Ctrl+C (for local)
```

### Code Quality Checks

**Before Committing:**

```bash
# Format code
poetry run ruff format app/

# Lint code
poetry run ruff check --fix app/

# Type check
poetry run mypy app/

# Run tests
poetry run pytest
```

**Pre-commit Hook:**

```bash
# Install once
poetry run pre-commit install

# Runs automatically on git commit
# Or run manually
poetry run pre-commit run --all-files
```

### Making Changes to Dependencies

**Adding New Dependency:**

```bash
# Add to pyproject.toml
poetry add package-name

# For dev dependencies
poetry add --group dev package-name

# Rebuild Docker image
./scripts/docker-dev.sh stop
docker-compose build
./scripts/docker-dev.sh start
```

**Updating Dependencies:**

```bash
# Update all dependencies
poetry update

# Update specific package
poetry update package-name

# Rebuild Docker
docker-compose build --no-cache
```

**Rebuild Docker Image:**

```bash
# Full rebuild
./scripts/docker-dev.sh clean
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start
```

### Working with Database Changes

Currently using in-memory job storage. For persistent storage:

1. Add database dependency (PostgreSQL/Redis)
2. Update `docker-compose.yml` with database service
3. Create migrations (if using SQLAlchemy)
4. Update configuration in `app/config.py`

### Hot Reloading

**Docker (enabled by default):**
- Code changes auto-reload
- Template changes auto-reload
- Config changes require restart: `./scripts/docker-dev.sh restart`

**Local:**
- Use `--reload` flag with uvicorn
- Auto-reloads on `.py` file changes

### Debugging

**Using Docker:**

```bash
# Access container shell
./scripts/docker-dev.sh shell

# Install ipdb for debugging
pip install ipdb

# Add breakpoint in code
import ipdb; ipdb.set_trace()

# Restart with attached terminal
docker-compose up
```

Inside container:

```python
# Add to your code for debugging
import ipdb; ipdb.set_trace()

# Or use builtin breakpoint()
breakpoint()
```

**Using VS Code Debugger:**
1. Set breakpoints in code
2. Use "FastAPI" launch configuration
3. Start debugging (F5)

**Using PyCharm Debugger:**
1. Set breakpoints
2. Right-click run configuration → Debug
3. Debugger attaches automatically

### Working with Git

**Branch Strategy:**
- `main` - Production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

**Commit Guidelines:**
- Use conventional commits format
- Include issue reference if applicable
- Run tests before pushing

**Pull Request Process:**
1. Create feature branch
2. Make changes and test locally
3. Push branch and create PR
4. Address Greptile review comments
5. Merge after approval

---

## Next Steps

After successful installation:

1. **Read Architecture Docs**: See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
2. **Try Sample Conversion**: Upload a LaTeX file via Web UI at http://localhost:8000
3. **Explore API Docs**: Visit http://localhost:8000/docs for interactive API documentation
4. **Run Full Test Suite**: Ensure all tests pass before making changes
5. **Set Up IDE**: Configure VS Code or PyCharm as described above
6. **Join Development**: Check GitHub Issues for open tasks

---

## Quick Reference

### Essential Commands

| Task | Docker | Local |
|------|--------|-------|
| Start | `./scripts/docker-dev.sh start` | `poetry run uvicorn app.main:app --reload` |
| Stop | `./scripts/docker-dev.sh stop` | Ctrl+C |
| Logs | `./scripts/docker-dev.sh logs` | Check terminal output |
| Tests | `./scripts/docker-dev.sh test` | `poetry run pytest` |
| Shell | `./scripts/docker-dev.sh shell` | N/A |
| Health | `curl http://localhost:8000/api/v1/health` | Same |
| Web UI | http://localhost:8000 | Same |
| API Docs | http://localhost:8000/docs | Same |

### Important Paths

| Path | Purpose |
|------|---------|
| `app/` | Application source code |
| `app/api/` | API endpoints |
| `app/services/` | Business logic services |
| `app/configs/` | Configuration schemas |
| `tests/` | Test files |
| `docs/` | Documentation |
| `uploads/` | Uploaded files (local dev) |
| `outputs/` | Conversion results (local dev) |
| `logs/` | Application logs |

### Useful Links

- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

---

*Last Updated: 2025-12-07*
*Version: 1.0*
