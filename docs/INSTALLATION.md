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

### 2. Configure Environment

### 3. Start Development Server

### 4. Verify Installation

**Check Service Health:**

Expected response:

**Access Web UI:**
Open browser to http://localhost:8000

**Test API:**

### 5. View Logs (Optional)

---

## Local Development Setup (Without Docker)

For developers who prefer running services natively on their machine.

### 1. Install System Dependencies

**macOS (using Homebrew):**

**Ubuntu/Debian:**

**Verify Installations:**

### 2. Install Python Dependencies

**Using Poetry (Recommended):**

**Using pip (Alternative):**

### 3. Create Required Directories

### 4. Configure Environment

Copy template and customize:

Edit `.env` and set local tool paths:

### 5. Start Development Server

**With auto-reload:**

**Production mode:**

### 6. Verify Installation

Test endpoint:

---

## Environment Configuration

### Configuration Files

- `.env` - Local environment variables (gitignored)
- `docker.env.template` - Template for Docker environment
- `app/config.py` - Application configuration schema
- `app/configs/latexml.py` - LaTeXML-specific settings

### Key Environment Variables

#### Application Settings

#### Server Configuration

#### File Upload Settings

#### External Tools (Docker Paths)

**For Local Development** (adjust to your installation):

#### Conversion Settings

#### Security Settings

**Production Requirements**:
- `SECRET_KEY` must be 64+ characters
- Generate with: `openssl rand -base64 48`

### Environment-Specific Configuration

**Development (.env):**

**Staging:**

**Production:**

---

## Running the Application

### Docker Commands

**Using Helper Script:**

**Using Docker Compose Directly:**

**View Container Logs:**

**Access Container Shell:**

### Local Commands

**Start Server:**

**Start with Custom Port:**

**Enable Debug Mode:**

**Run in Background:**

---

## Running Tests

### Docker Environment

**Run All Tests:**

**Run Specific Test File:**

**Run with Coverage:**

**Run Integration Tests Only:**

### Local Environment

**Using Poetry:**

**Using pytest Directly:**

**Watch Mode (auto-rerun on changes):**

**Generate Coverage Report:**

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

**Settings (.vscode/settings.json):**

**Launch Configuration (.vscode/launch.json):**

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

**MyPy (Type Checker):**

**Pre-commit Hooks:**

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails

**Problem:** Docker build fails with "out of space" error

**Solution:**

#### 2. Port Already in Use

**Problem:** Error "Address already in use" on port 8000

**Solution:**

#### 3. LaTeXML Not Found

**Problem:** "latexmlc: command not found"

**Solution (Docker):**

**Solution (Local):**

#### 4. Permission Denied Errors

**Problem:** Cannot write to uploads/outputs directories

**Solution (Docker):**

**Solution (Local):**

#### 5. Package Installation Fails

**Problem:** tlmgr fails to install LaTeX packages

**Solution:**

#### 6. Conversion Timeouts

**Problem:** Conversions timing out after 300s

**Solution:**

#### 7. Memory Issues with Large Documents

**Problem:** Container crashes with large LaTeX projects

**Solution:**

#### 8. Python Version Mismatch

**Problem:** "Python 3.11+ required" error

**Solution:**

### Health Check Failures

**Check Service Status:**

**Inspect Logs:**

**Verify Tool Availability:**

**Test External Tools:**

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

**Report Issues:**
1. Include error logs from above commands
2. Include system info: OS, Docker version, Python version
3. Provide minimal reproduction case
4. Submit to GitHub Issues: https://github.com/istealersn-dev/latex-html-converter/issues

---

## Development Workflow

### Daily Development Cycle

**1. Start Services:**

**2. Make Code Changes:**
- Edit files in `app/` directory
- Changes auto-reload (Docker with `--reload` flag)
- No rebuild needed for code changes

**3. Test Changes:**

**4. View Logs:**

**5. Stop Services:**

### Code Quality Checks

**Before Committing:**

**Pre-commit Hook:**

### Making Changes to Dependencies

**Adding New Dependency:**

**Updating Dependencies:**

**Rebuild Docker Image:**

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

Inside container:

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
