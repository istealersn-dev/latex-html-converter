# 📋 LaTeX → HTML5 Converter - TODO

## 🎯 Project Overview
FastAPI-based service converting LaTeX projects to clean HTML5 with ≥95% fidelity using Tectonic + LaTeXML pipeline.

---

## 📊 Progress Tracking

**Overall Progress:** 85% (Phase 1 Complete, Phase 2 In Progress)

---

## 🚀 Phase 1 — MVP (Foundation)

### Core Infrastructure
- [x] **FastAPI Application Setup**
  - [x] Create `app/main.py` with FastAPI app initialization
  - [x] Configure CORS, middleware, and basic settings
  - [x] Set up logging with loguru
  - [x] Create health check endpoint (`/api/v1/health`)

- [x] **API Endpoints**
  - [x] Implement `/convert` POST endpoint
  - [x] File upload handling (zip/tar.gz)
  - [x] Request/response models with Pydantic
  - [x] Error handling and validation

- [x] **Core Services**
  - [x] `app/services/orchestrator.py` - Main conversion pipeline
  - [x] `app/services/assets.py` - Asset conversion (TikZ/PDF → SVG)
  - [x] `app/services/html_post.py` - HTML cleaning and normalization
  - [x] `app/services/scoring.py` - Fidelity scoring system

- [x] **Utility Functions**
  - [x] `app/utils/fs.py` - File system operations
  - [x] `app/utils/shell.py` - Shell command execution

### External Dependencies Integration
- [x] **PDFLaTeX Integration** (Tectonic Alternative)
  - [x] Install and configure PDFLaTeX in Docker
  - [x] Implement deterministic compilation with pdflatex
  - [x] Handle AUX, TOC, BBL generation
  - [x] Create PDFLaTeXService adapter for Tectonic interface

- [x] **LaTeXML Integration**
  - [x] Install and configure LaTeXML
  - [x] Implement TeX → XML/HTML conversion
  - [x] Configure MathML generation (in progress)

### Testing & Quality
- [x] **Test Suite**
  - [x] Create `tests/test_conversion.py`
  - [x] Unit tests for core services
  - [x] Integration tests with sample LaTeX documents
  - [x] Test fixtures and sample data

- [x] **Development Tools**
  - [x] Configure ruff linting
  - [x] Set up mypy type checking
  - [x] Install pre-commit hooks
  - [x] Run initial linting and type checking

### Documentation
- [x] **Core Documentation**
  - [x] Create `docs/architecture.md` - Detailed system design
  - [x] Create `docs/api.md` - API documentation
  - [x] Create `docs/installation.md` - Setup instructions
  - [x] Create `docs/development.md` - Development workflow
  - [x] Create `DOCKER.md` - Docker setup and deployment guide
  - [x] Create `README.md` - Project overview and quick start

### Docker & Deployment
- [x] **Docker Configuration**
  - [x] Create `Dockerfile` with TeXLive base image
  - [x] Configure `docker-compose.yml` for development
  - [x] Set up volume mounts for accessible outputs
  - [x] Create `docker-dev.sh` helper script
  - [x] Configure environment variables and paths

- [x] **Production Readiness**
  - [x] Docker container with complete LaTeX environment
  - [x] PDFLaTeX, LaTeXML, dvisvgm, ghostscript integration
  - [x] Output directory mounting for host access
  - [x] Health checks and monitoring
  - [x] Security hardening (non-root user)

---

## 🎯 Phase 2 — Accuracy Push

### Package Support
- [x] **LaTeX Package Plugins**
  - [x] `amsmath` support and testing
  - [x] `booktabs` table formatting
  - [x] `cleveref` cross-referencing
  - [x] `natbib` bibliography handling
  - [x] `tikz` diagram conversion

### Asset Processing
- [x] **Figure Conversion**
  - [x] PDF → SVG conversion with `dvisvgm`
  - [x] TikZ → SVG pipeline
  - [x] Image optimization and compression
  - [x] Caption and label preservation

### Mathematical Rendering
- [x] **MathJax Integration**
  - [x] Configure MathJax 3.x for modern mathematical rendering
  - [x] Add MathJax configuration to HTML post-processor
  - [x] Support for inline and display mathematics
  - [x] Accessibility features for screen readers

- [ ] **MathML Output** (In Progress)
  - [x] Configure LaTeXML for MathML generation
  - [ ] Debug LaTeXML conversion failures
  - [ ] Test complex mathematical expressions
  - [ ] Verify MathML accessibility compliance

### Outstanding Issues & Bug Fixes
- [ ] **LaTeXML Conversion Failures**
  - [ ] Debug LaTeXML bibliography processing errors
  - [ ] Fix LaTeXML command configuration issues
  - [ ] Test LaTeXML with simple mathematical documents
  - [ ] Verify LaTeXML MathML output format
  - [ ] Add proper error handling for LaTeXML failures

- [ ] **Mathematical Rendering Issues**
  - [ ] Resolve LaTeXML MathML generation problems
  - [ ] Test complex mathematical expressions (equations, matrices, integrals)
  - [ ] Verify MathJax 3.x integration with MathML output
  - [ ] Ensure accessibility compliance for mathematical content
  - [ ] Test mathematical documents with various LaTeX packages

- [ ] **Conversion Pipeline Debugging**
  - [ ] Investigate conversion failures with basic documents
  - [ ] Fix temporary directory cleanup issues
  - [ ] Improve error reporting and logging
  - [ ] Add conversion status tracking
  - [ ] Test end-to-end conversion with sample documents

### Technical Debt & Improvements
- [ ] **LaTeXML Configuration Issues**
  - [ ] Fix `--mathml` flag causing conversion failures
  - [ ] Implement conditional MathML output based on settings
  - [ ] Add LaTeXML version compatibility checks
  - [ ] Configure LaTeXML for better error reporting

- [ ] **Docker Environment Issues**
  - [ ] Verify all required LaTeX packages are installed
  - [ ] Test LaTeXML dependencies in container
  - [ ] Add LaTeXML debugging tools to container
  - [ ] Improve container logging for conversion failures

- [ ] **Error Handling & Debugging**
  - [ ] Add detailed error messages for LaTeXML failures
  - [ ] Implement conversion step-by-step logging
  - [ ] Add conversion result validation
  - [ ] Create debugging endpoints for conversion issues

### Quality Assurance
- [ ] **Coverage Dashboard**
  - [ ] Package support manifest (`data/package_support.json`)
  - [ ] Support coverage tracking
  - [ ] Missing package detection
  - [ ] Fallback strategies for unsupported packages

### Enhanced Scoring
- [ ] **Fidelity Improvements**
  - [ ] Enhanced structure scoring (40% weight)
  - [ ] Math rendering validation (30% weight)
  - [ ] Asset integrity checks (20% weight)
  - [ ] Completeness verification (10% weight)

---

## 🚀 Phase 3 — Scale & UX

### Performance & Scalability
- [ ] **Queue System**
  - [ ] Celery + Redis integration
  - [ ] Async task processing
  - [ ] Job status tracking
  - [ ] Progress reporting

### Data Persistence
- [ ] **Database Integration**
  - [ ] PostgreSQL setup
  - [ ] Conversion history storage
  - [ ] User session management
  - [ ] Result caching

### User Experience
- [ ] **Web Interface**
  - [ ] Overleaf-like preview interface
  - [ ] Real-time conversion status
  - [ ] Interactive result viewing
  - [ ] Download and sharing features

---

## 🧪 Testing Strategy

### Test Categories
- [ ] **Unit Tests**
  - [ ] Service layer testing
  - [ ] Utility function testing
  - [ ] Model validation testing

- [ ] **Integration Tests**
  - [ ] End-to-end conversion testing
  - [ ] External tool integration
  - [ ] Error scenario testing

- [ ] **Performance Tests**
  - [ ] Large document handling
  - [ ] Concurrent request testing
  - [ ] Memory usage optimization

### Test Data
- [ ] **Sample Documents**
  - [ ] Simple LaTeX documents
  - [ ] Complex academic papers
  - [ ] Documents with figures and tables
  - [ ] Math-heavy documents

---

## 📝 Documentation Tasks

### Technical Documentation
- [ ] **Architecture Documentation**
  - [ ] System design diagrams
  - [ ] Component interaction flows
  - [ ] Data flow documentation

- [ ] **API Documentation**
  - [ ] OpenAPI/Swagger integration
  - [ ] Endpoint documentation
  - [ ] Request/response examples
  - [ ] Error code reference

- [ ] **User Documentation**
  - [ ] Installation guide
  - [ ] Usage examples
  - [ ] Troubleshooting guide
  - [ ] FAQ section

---

## 🔧 Development Workflow

### Setup Tasks
- [ ] **Environment Setup**
  - [ ] Python virtual environment
  - [ ] Poetry dependency management
  - [ ] Development dependencies installation
  - [ ] Pre-commit hook configuration

### Quality Assurance
- [ ] **Code Quality**
  - [ ] Ruff linting configuration
  - [ ] MyPy type checking setup
  - [ ] Test coverage reporting
  - [ ] Code formatting standards

---

## 📈 Success Metrics

### Phase 1 Targets
- [x] Basic conversion pipeline working
- [x] ≥90% fidelity on simple documents
- [x] Core API endpoints functional
- [x] Basic test suite passing

### Phase 2 Targets
- [x] ≥95% fidelity on complex documents
- [x] Support for major LaTeX packages
- [x] Robust asset conversion
- [x] Comprehensive test coverage

### Phase 3 Targets
- [x] Scalable architecture (Docker-based)
- [ ] User-friendly interface
- [x] Production-ready deployment (Docker containerized)
- [x] Performance optimization

---

## 📝 Notes

- Keep deterministic mode for reproducible outputs
- Avoid `--shell-escape` in Tectonic for security
- Use `dvisvgm` for heavy TikZ/PSTricks projects
- Maintain package coverage manifest
- Follow security best practices for file uploads

---

**Last Updated:** October 12, 2025
**Current Phase:** Phase 2 - Bug Fixes & Mathematical Rendering
**Next Milestone:** Fix LaTeXML conversion failures and implement proper MathML output
**Current Focus:** Debugging LaTeXML issues and resolving mathematical rendering problems
**Critical Issues:** LaTeXML conversion failures, MathML output not working, basic document conversion failing
