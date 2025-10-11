# 📋 LaTeX → HTML5 Converter - TODO

## 🎯 Project Overview
FastAPI-based service converting LaTeX projects to clean HTML5 with ≥95% fidelity using Tectonic + LaTeXML pipeline.

---

## 📊 Progress Tracking

**Overall Progress:** 0% (Project Initialization)

---

## 🚀 Phase 1 — MVP (Foundation)

### Core Infrastructure
- [ ] **FastAPI Application Setup**
  - [ ] Create `app/main.py` with FastAPI app initialization
  - [ ] Configure CORS, middleware, and basic settings
  - [ ] Set up logging with loguru
  - [ ] Create health check endpoint (`/healthz`)

- [ ] **API Endpoints**
  - [ ] Implement `/convert` POST endpoint
  - [ ] File upload handling (zip/tar.gz)
  - [ ] Request/response models with Pydantic
  - [ ] Error handling and validation

- [ ] **Core Services**
  - [ ] `app/services/orchestrator.py` - Main conversion pipeline
  - [ ] `app/services/assets.py` - Asset conversion (TikZ/PDF → SVG)
  - [ ] `app/services/html_post.py` - HTML cleaning and normalization
  - [ ] `app/services/scoring.py` - Fidelity scoring system

- [ ] **Utility Functions**
  - [ ] `app/utils/fs.py` - File system operations
  - [ ] `app/utils/shell.py` - Shell command execution

### External Dependencies Integration
- [ ] **Tectonic Integration**
  - [ ] Install and configure Tectonic
  - [ ] Implement deterministic compilation
  - [ ] Handle AUX, TOC, BBL generation

- [ ] **LaTeXML Integration**
  - [ ] Install and configure LaTeXML
  - [ ] Implement TeX → XML/HTML conversion
  - [ ] Handle MathML generation

### Testing & Quality
- [ ] **Test Suite**
  - [ ] Create `tests/test_conversion.py`
  - [ ] Unit tests for core services
  - [ ] Integration tests with sample LaTeX documents
  - [ ] Test fixtures and sample data

- [ ] **Development Tools**
  - [ ] Configure ruff linting
  - [ ] Set up mypy type checking
  - [ ] Install pre-commit hooks
  - [ ] Run initial linting and type checking

### Documentation
- [ ] **Core Documentation**
  - [ ] Create `docs/architecture.md` - Detailed system design
  - [ ] Create `docs/api.md` - API documentation
  - [ ] Create `docs/installation.md` - Setup instructions
  - [ ] Create `docs/development.md` - Development workflow

---

## 🎯 Phase 2 — Accuracy Push

### Package Support
- [ ] **LaTeX Package Plugins**
  - [ ] `amsmath` support and testing
  - [ ] `booktabs` table formatting
  - [ ] `cleveref` cross-referencing
  - [ ] `natbib` bibliography handling
  - [ ] `tikz` diagram conversion

### Asset Processing
- [ ] **Figure Conversion**
  - [ ] PDF → SVG conversion with `dvisvgm`
  - [ ] TikZ → SVG pipeline
  - [ ] Image optimization and compression
  - [ ] Caption and label preservation

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
- [ ] Basic conversion pipeline working
- [ ] ≥90% fidelity on simple documents
- [ ] Core API endpoints functional
- [ ] Basic test suite passing

### Phase 2 Targets
- [ ] ≥95% fidelity on complex documents
- [ ] Support for major LaTeX packages
- [ ] Robust asset conversion
- [ ] Comprehensive test coverage

### Phase 3 Targets
- [ ] Scalable architecture
- [ ] User-friendly interface
- [ ] Production-ready deployment
- [ ] Performance optimization

---

## 📝 Notes

- Keep deterministic mode for reproducible outputs
- Avoid `--shell-escape` in Tectonic for security
- Use `dvisvgm` for heavy TikZ/PSTricks projects
- Maintain package coverage manifest
- Follow security best practices for file uploads

---

**Last Updated:** [Current Date]
**Current Phase:** Phase 1 - MVP Foundation
**Next Milestone:** FastAPI Application Setup
