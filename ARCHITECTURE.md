# LaTeX to HTML5 Converter - Architecture Documentation

## Overview

The LaTeX to HTML5 Converter is a microservice that transforms LaTeX documents into high-quality HTML5 output. It uses a multi-stage pipeline approach with Tectonic (PDFLaTeX) for compilation, LaTeXML for conversion, and custom post-processing for optimization and enhancement.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   API Layer   │  │  Health API  │  │  Debug API    │         │
│  │  (REST)       │  │  (Monitoring)│  │  (Diagnostics)│         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                    │
│                   ┌─────────▼─────────┐                         │
│                   │  Conversion API   │                         │
│                   │  (conversion.py) │                         │
│                   └─────────┬─────────┘                         │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Conversion Orchestrator                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  • Job Scheduling & Resource Management                   │ │
│  │  • Concurrent Job Control (max 5 jobs)                    │ │
│  │  • Job Lifecycle Management                               │ │
│  │  • Background Task Coordination                           │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Conversion Pipeline                          │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Stage 1: File Discovery & Project Analysis              │ │
│  │  Stage 2: Tectonic/PDFLaTeX Compilation                  │ │
│  │  Stage 3: LaTeXML Conversion                             │ │
│  │  Stage 4: HTML Post-Processing                           │ │
│  │  Stage 5: Validation & Quality Assessment                │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Conversion Pipeline Flow

### Detailed Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT: LaTeX Archive                         │
│                    (.zip, .tar.gz, .tar)                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  File Upload & Extract│
                    │  • Archive validation │
                    │  • Extraction         │
                    │  • Security checks    │
                    └───────────┬───────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1: File Discovery & Project Analysis                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FileDiscoveryService                                         │  │
│  │  • Identify main .tex file                                    │  │
│  │  • Discover project structure                                 │  │
│  │  • Detect custom document classes                             │  │
│  │  • Analyze LaTeX dependencies                                 │  │
│  │  • Package detection                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PackageManagerService                                        │  │
│  │  • Detect missing packages                                    │  │
│  │  • Auto-install via tlmgr/apt-get                              │  │
│  │  • Package mapping & resolution                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2: Tectonic/PDFLaTeX Compilation                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PDFLaTeXService (Tectonic fallback)                         │  │
│  │  • LaTeX compilation                                          │  │
│  │  • Generate AUX, TOC, BBL files                              │  │
│  │  • Error detection & reporting                                │  │
│  │  • Fallback to LaTeXML-only if fails                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  Output: Compiled LaTeX + Metadata                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3: LaTeXML Conversion                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  LaTeXMLService                                               │  │
│  │  • TeX → HTML/XML conversion                                  │  │
│  │  • MathML generation                                           │  │
│  │  • CSS/JavaScript inclusion                                    │  │
│  │  • Custom class path resolution                               │  │
│  │  • Project directory integration                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  Output: Raw HTML with MathML, CSS, Assets                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 4: HTML Post-Processing                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  HTMLPostProcessor                                            │  │
│  │  Step 1: HTML Cleaning                                         │  │
│  │    • Remove unsafe elements                                   │  │
│  │    • Sanitize content                                          │  │
│  │  Step 2: Structure Validation                                  │  │
│  │    • Validate HTML structure                                  │  │
│  │    • Check document integrity                                 │  │
│  │  Step 3: Asset Conversion                                     │  │
│  │    • TikZ → SVG (via AssetConversionService)                  │  │
│  │    • PDF → SVG (via dvisvgm)                                  │  │
│  │  Step 4: Enhancement                                          │  │
│  │    • Fix image paths                                          │  │
│  │    • Add MathJax support                                      │  │
│  │    • Process math expressions                                 │  │
│  │    • Enhance links                                            │  │
│  │    • Add responsive meta tags                                  │  │
│  │  Step 5: Optimization                                         │  │
│  │    • Minify HTML                                              │  │
│  │    • Optimize structure                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 5: Validation & Quality Assessment                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • Output file validation                                     │  │
│  │  • Quality scoring                                            │  │
│  │  • Error/warning collection                                   │  │
│  │  • Metadata generation                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   OUTPUT: final.html   │
                    │   + Assets + Report    │
                    └───────────────────────┘
```

## Component Architecture

### Core Services

#### 1. ConversionOrchestrator
**Purpose**: High-level job management and coordination

**Responsibilities**:
- Job creation and lifecycle management
- Resource limit enforcement (max concurrent jobs)
- Background task scheduling
- Job status tracking and monitoring
- Automatic cleanup of completed jobs
- Stuck job detection and recovery

**Key Methods**:
- `start_conversion()`: Create and start a new conversion job
- `get_job_status()`: Retrieve current job status
- `get_job_progress()`: Get detailed progress information
- `get_job_result()`: Retrieve final conversion result
- `cancel_job()`: Cancel a running job

#### 2. ConversionPipeline
**Purpose**: Execute the multi-stage conversion process

**Responsibilities**:
- Coordinate pipeline stages sequentially
- Manage job state and progress tracking
- Handle stage failures and error recovery
- Collect diagnostics and metadata
- Generate conversion results

**Pipeline Stages**:
1. **File Discovery**: Analyze project structure
2. **Tectonic Compilation**: Compile LaTeX to PDF
3. **LaTeXML Conversion**: Convert TeX to HTML
4. **HTML Post-Processing**: Clean and enhance HTML
5. **Validation**: Verify output quality

#### 3. FileDiscoveryService
**Purpose**: Analyze LaTeX project structure

**Responsibilities**:
- Identify main LaTeX file
- Discover project dependencies
- Detect custom document classes
- Extract bibliography files
- Map project structure

#### 4. PackageManagerService
**Purpose**: Manage LaTeX package dependencies

**Responsibilities**:
- Detect missing packages from LaTeX source
- Auto-install packages via `tlmgr` or `apt-get`
- Map package names to installation commands
- Handle package installation failures gracefully
- Log package installation attempts

#### 5. PDFLaTeXService
**Purpose**: Compile LaTeX documents

**Responsibilities**:
- Execute PDFLaTeX/Tectonic compilation
- Generate auxiliary files (AUX, TOC, BBL)
- Detect compilation errors
- Provide fallback mechanisms
- Extract compilation metadata

#### 6. LaTeXMLService
**Purpose**: Convert LaTeX to HTML/XML

**Responsibilities**:
- Execute LaTeXML conversion commands
- Configure LaTeXML options (MathML, CSS, JS)
- Handle custom document classes
- Process project directory paths
- Parse conversion results and warnings

#### 7. HTMLPostProcessor
**Purpose**: Clean and enhance HTML output

**Responsibilities**:
- Clean unsafe HTML elements
- Validate HTML structure
- Convert assets (TikZ, PDF) to SVG
- Fix image paths relative to output location
- Add MathJax support for math rendering
- Enhance links and add responsive meta tags
- Optimize HTML structure

#### 8. AssetConversionService
**Purpose**: Convert graphics to SVG format

**Responsibilities**:
- Convert TikZ diagrams to SVG
- Convert PDF figures to SVG
- Optimize SVG output
- Validate converted assets

## Data Flow

### Request Flow

```
Client Request
    │
    ▼
FastAPI Router (conversion.py)
    │
    ▼
File Upload & Validation
    │
    ▼
ConversionOrchestrator.start_conversion()
    │
    ▼
ConversionPipeline.create_conversion_job()
    │
    ▼
Background Task (ThreadPoolExecutor)
    │
    ▼
ConversionPipeline.execute_pipeline()
    │
    ├─► FileDiscoveryService
    ├─► PackageManagerService
    ├─► PDFLaTeXService
    ├─► LaTeXMLService
    ├─► HTMLPostProcessor
    └─► Validation
    │
    ▼
ConversionResult
    │
    ▼
Storage (in-memory + file system)
    │
    ▼
API Response (status/result/download)
```

### File System Structure

```
project_root/
├── uploads/
│   └── {job_id}/
│       ├── {archive}.zip
│       └── extracted/
│           ├── main.tex
│           ├── figures/
│           ├── references.bib
│           └── ...
│
└── outputs/
    └── {zip_name}_{job_id}/
        ├── final.html              # Final processed HTML
        ├── latexml/
        │   ├── main.html           # LaTeXML raw output
        │   ├── LaTeXML.css         # LaTeXML stylesheet
        │   ├── ltx-article.css     # Article stylesheet
        │   └── figures/            # Image assets
        │       ├── figure-1.png
        │       └── figure-2.png
        └── tectonic/               # Tectonic output (if used)
            └── main.pdf
```

## External Dependencies

### System Tools (Docker Container)

#### LaTeX Distribution
- **TeXLive**: Full LaTeX distribution
  - `texlive-full`: Complete TeXLive installation
  - `texlive-science`: Scientific packages
  - `texlive-publishers`: Publisher-specific packages
  - `texlive-bibtex-extra`: Bibliography tools
  - `texlive-latex-extra`: Additional LaTeX packages
  - `texlive-fonts-extra`: Extended font support
  - `texlive-latex-recommended`: Recommended packages
  - `texlive-lang-english`: English language support

#### Conversion Tools
- **Tectonic/PDFLaTeX**: LaTeX compilation engine
  - Path: `/usr/local/bin/tectonic` (symlink to `/usr/bin/pdflatex`)
  - Purpose: Compile LaTeX to PDF and generate auxiliary files

- **LaTeXML**: LaTeX to XML/HTML converter
  - Path: `/usr/bin/latexmlc` (HTML) or `/usr/bin/latexml` (XML)
  - Purpose: Convert LaTeX source to HTML5 with MathML

- **dvisvgm**: DVI to SVG converter
  - Path: `/usr/bin/dvisvgm`
  - Purpose: Convert DVI files to SVG format

- **Ghostscript**: PDF processing
  - Path: `/usr/bin/gs`
  - Purpose: PDF manipulation and conversion

- **Poppler Utils**: PDF utilities
  - Purpose: PDF processing and extraction

#### Package Management
- **tlmgr**: TeXLive package manager
  - Purpose: Install LaTeX packages on-demand
  - Repository: CTAN mirror

- **apt-get**: Debian package manager
  - Purpose: Install system packages (fallback)

### Python Libraries

#### Web Framework
- **FastAPI** (^0.115.0): Modern async web framework
  - Purpose: REST API endpoints, request/response handling
  - Features: Automatic OpenAPI docs, async support, validation

- **Uvicorn** (^0.30.0): ASGI server
  - Purpose: Run FastAPI application
  - Features: Hot-reload, multiple workers, production-ready

#### Data Validation & Settings
- **Pydantic** (^2.9.0): Data validation using Python type annotations
  - Purpose: Request/response models, settings management
  - Features: Type validation, serialization, field validation

- **Pydantic Settings** (^2.5.2): Settings management
  - Purpose: Environment variable configuration
  - Features: Automatic env var parsing, type conversion

#### HTML Processing
- **BeautifulSoup4** (^4.12.3): HTML/XML parser
  - Purpose: Parse and manipulate HTML documents
  - Features: DOM traversal, element modification, content extraction

- **lxml** (^5.2.2): XML/HTML processing library
  - Purpose: Fast XML/HTML parsing and validation
  - Features: XPath support, HTML cleaning, validation

#### File Handling
- **aiofiles** (^23.2.1): Async file operations
  - Purpose: Asynchronous file I/O
  - Features: Non-blocking file operations

- **python-multipart** (^0.0.9): Multipart form data parsing
  - Purpose: Handle file uploads
  - Features: Form data parsing, file upload support

#### Graphics Processing
- **CairoSVG** (^2.8.2): SVG to PNG/PDF converter
  - Purpose: Convert SVG to raster formats
  - Features: High-quality rendering, format conversion

- **Pillow** (^11.3.0): Image processing library
  - Purpose: Image manipulation and optimization
  - Features: Format conversion, resizing, optimization

- **svgwrite** (^1.4.3): SVG generation
  - Purpose: Programmatic SVG creation
  - Features: SVG element creation, styling

#### LaTeX Utilities
- **pylatexenc** (^2.10): LaTeX utilities
  - Purpose: LaTeX parsing and manipulation
  - Features: Command parsing, encoding handling

#### System Utilities
- **psutil** (^7.1.0): System and process utilities
  - Purpose: Resource monitoring, process management
  - Features: CPU/memory monitoring, process control

#### Logging
- **loguru** (^0.7.2): Advanced logging library
  - Purpose: Structured logging throughout the application
  - Features: Color output, file rotation, structured logs

## Service Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Request Handler                        │
│                    (app/api/conversion.py)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ConversionOrchestrator                      │
│  • Job ID generation                                            │
│  • Resource limit checking                                      │
│  • Background task scheduling                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ConversionPipeline                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Stage 1: File Discovery                                  │  │
│  │    └─► FileDiscoveryService                              │  │
│  │         └─► PackageManagerService                         │  │
│  │                                                           │  │
│  │  Stage 2: Tectonic Compilation                            │  │
│  │    └─► PDFLaTeXService                                    │  │
│  │                                                           │  │
│  │  Stage 3: LaTeXML Conversion                              │  │
│  │    └─► LaTeXMLService                                    │  │
│  │         └─► LaTeXMLSettings (config)                      │  │
│  │                                                           │  │
│  │  Stage 4: HTML Post-Processing                            │  │
│  │    └─► HTMLPostProcessor                                 │  │
│  │         ├─► AssetConversionService (optional)            │  │
│  │         │    ├─► TikZConversionService                   │  │
│  │         │    └─► PDFConversionService                    │  │
│  │         └─► AssetValidator                               │  │
│  │                                                           │  │
│  │  Stage 5: Validation                                      │  │
│  │    └─► Output validation & quality scoring               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ConversionResult                            │
│  • HTML file path                                               │
│  • Asset files list                                             │
│  • Conversion report                                            │
│  • Quality metrics                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Management

### Settings Hierarchy

```
Environment Variables
    │
    ▼
app/config.py (Settings)
    ├─► External tool paths (TECTONIC_PATH, LATEXML_PATH, etc.)
    ├─► Conversion settings (timeout, max concurrent jobs)
    ├─► File paths (UPLOAD_DIR, OUTPUT_DIR)
    └─► Security settings
    │
    ▼
app/configs/latexml.py (LaTeXMLSettings)
    ├─► LaTeXML executable path
    ├─► Output format options
    ├─► MathML/CSS/JS inclusion flags
    └─► Package management settings
```

### Environment Variable Prefixes

- **Main Settings**: Direct variable names (e.g., `LATEXML_PATH`, `TECTONIC_PATH`)
- **LaTeXML Settings**: `LATEXML_` prefix (e.g., `LATEXML_LATEXML_PATH`, `LATEXML_OUTPUT_FORMAT`)

## Error Handling & Recovery

### Error Propagation Flow

```
Service Error
    │
    ▼
Custom Exception (e.g., LaTeXMLConversionError)
    │
    ▼
Pipeline Stage Failure
    │
    ├─► Log error with context
    ├─► Update job status to FAILED
    ├─► Collect error diagnostics
    └─► Attempt fallback (if configured)
    │
    ▼
ConversionResult with error information
```

### Fallback Mechanisms

1. **Tectonic Failure**: Fallback to LaTeXML-only conversion
2. **Package Installation Failure**: Continue with available packages
3. **Asset Conversion Failure**: Skip asset conversion, use original format
4. **HTML Processing Failure**: Return raw LaTeXML output

## Resource Management

### Concurrent Job Limits

- **Maximum Concurrent Jobs**: 5 (configurable)
- **Job Timeout**: 600 seconds (10 minutes, configurable)
- **Cleanup Interval**: 3600 seconds (1 hour)

### Resource Monitoring

- Active job tracking
- Stuck job detection
- Automatic cleanup of completed jobs
- Resource limit enforcement

## Security Considerations

### Input Validation

- Archive file validation (ZIP safety checks)
- LaTeX file content validation
- Path traversal prevention
- Command injection prevention

### Command Execution Safety

- Shell command sanitization
- Allowed command whitelist
- Path validation
- Timeout enforcement

### File System Security

- Restricted file access
- Temporary file cleanup
- Output directory isolation

## Storage Architecture

### In-Memory Storage

- **Job Tracking**: Active jobs dictionary
- **Conversion Metadata**: Job status, progress, results
- **Limitation**: Lost on service restart (production should use database)

### File System Storage

- **Uploads**: Temporary storage for uploaded archives
- **Outputs**: Final HTML files and assets
- **Naming Convention**: `{zip_name}_{conversion_id}/`

## API Endpoints

### Conversion Endpoints

- `POST /api/v1/convert`: Upload and start conversion
- `GET /api/v1/convert/{conversion_id}`: Get conversion status
- `GET /api/v1/convert/{conversion_id}/result`: Get full conversion result
- `GET /api/v1/convert/{conversion_id}/download`: Download result as ZIP

### Health & Monitoring

- `GET /api/v1/health`: Service health check
- `GET /api/v1/debug/system`: System diagnostics
- `GET /api/v1/debug/conversions`: List active conversions

## Deployment Architecture

### Docker Container Structure

```
Docker Image (Debian-based)
├── Python 3.11+
├── TeXLive (full distribution)
├── LaTeXML
├── System tools (dvisvgm, ghostscript, poppler-utils)
└── Application code
```

### Production Considerations

- **Persistent Volumes**: For uploads, outputs, and logs
- **Resource Limits**: CPU and memory constraints
- **Health Checks**: Automated service monitoring
- **Logging**: Structured logging with rotation
- **Multiple Workers**: Uvicorn workers for concurrency

## Performance Characteristics

### Conversion Times

- **Simple Documents**: 5-10 seconds
- **Complex Academic Papers**: 15-30 seconds
- **With Fallback**: 20-40 seconds

### Resource Usage

- **Memory**: ~8GB for full TeXLive installation
- **CPU**: Variable based on document complexity
- **Storage**: Temporary files cleaned up automatically

## Future Enhancements

### Recommended Improvements

1. **Database Integration**: Replace in-memory storage with persistent database
2. **Caching Layer**: Cache conversion results for identical inputs
3. **Queue System**: Use message queue (Redis/RabbitMQ) for job management
4. **Distributed Processing**: Scale across multiple containers
5. **Result Storage**: Long-term storage for conversion results
6. **Monitoring**: Integration with monitoring tools (Prometheus, Grafana)

