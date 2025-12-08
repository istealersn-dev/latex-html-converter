# What Does Tectonic Do in the Code?

## Overview

**Tectonic** (or more accurately, the "Tectonic stage") is the **first stage** of the LaTeX to HTML conversion pipeline. It serves as a **validation and compilation step** that compiles LaTeX documents to PDF before the actual HTML conversion.

## Purpose

### Primary Functions:

1. **LaTeX Syntax Validation**: Validates that the LaTeX document is syntactically correct
2. **PDF Compilation**: Compiles the LaTeX document to PDF format
3. **Package Validation**: Ensures all required LaTeX packages are available
4. **Error Detection**: Catches LaTeX compilation errors early in the pipeline

### Why It's Used:

- **Early Error Detection**: Catches LaTeX syntax errors before HTML conversion
- **Package Verification**: Ensures all dependencies are installed
- **Quality Assurance**: Validates that the LaTeX document can be compiled successfully
- **Fallback Mechanism**: If Tectonic fails, the pipeline can continue with LaTeXML-only conversion

## Implementation Details

### Current Setup

**Important Note**: In the current Docker setup, "Tectonic" is actually **pdflatex** under the hood:

```dockerfile
# From Dockerfile line 42:
RUN ln -sf /usr/bin/pdflatex /usr/local/bin/tectonic
```

The codebase was designed to use **Tectonic** (a modern, Rust-based LaTeX compiler), but the Docker image uses **pdflatex** as a substitute via a symbolic link. The `PDFLaTeXService` provides a "Tectonic-compatible interface" that adapts Tectonic-specific flags to work with traditional pdflatex.

### Service Classes

1. **`TectonicService`** (`app/services/tectonic.py`):
   - Designed for the actual Tectonic compiler
   - Provides deterministic compilation with security features
   - Uses `--untrusted` flag for security

2. **`PDFLaTeXService`** (`app/services/pdflatex.py`):
   - **Currently Used**: Provides Tectonic-compatible interface using pdflatex
   - Adapts Tectonic flags to pdflatex equivalents
   - Used as the "tectonic_service" in the pipeline

## Pipeline Stage: Tectonic Compilation

### Stage 1: Tectonic Compilation

**Location**: `app/services/pipeline.py` - `_execute_tectonic_stage()`

**Steps Performed**:

1. **File Discovery**:
   - Extracts project files from ZIP (if applicable)
   - Discovers main .tex file and dependencies
   - Analyzes project structure

2. **Package Detection**:
   - Detects required LaTeX packages from source code
   - Checks package availability on system

3. **Package Installation**:
   - Automatically installs missing packages via `tlmgr`
   - Handles installation failures gracefully

4. **LaTeX Compilation**:
   - Compiles LaTeX to PDF using pdflatex (via Tectonic interface)
   - Validates syntax and structure
   - Generates PDF output

**Output**: 
- PDF file (stored in `outputs/{job_id}/tectonic/`)
- Compilation logs
- Validation report

**Fallback Behavior**:
- If Tectonic/pdflatex compilation fails, the stage is marked as `SKIPPED`
- Pipeline continues with LaTeXML-only conversion
- This ensures the conversion can proceed even if PDF compilation fails

## Code Flow

```
Conversion Pipeline
    ↓
Stage 1: Tectonic Compilation
    ├─→ File Discovery Service
    ├─→ Package Manager Service
    └─→ PDFLaTeXService (pdflatex with Tectonic interface)
        ↓
    PDF Output (optional)
    ↓
Stage 2: LaTeXML Conversion (continues regardless of Tectonic result)
```

## Configuration

**Settings**:
- `TECTONIC_PATH`: Path to Tectonic executable (default: `/usr/local/bin/tectonic`)
- `PDFLATEX_PATH`: Path to pdflatex (default: `/usr/bin/pdflatex`)
- In Docker: `TECTONIC_PATH` points to pdflatex via symlink

**Options**:
- `tectonic_options`: Compilation options (engine, format, extra args)
- Timeout: 300 seconds (5 minutes) default

## Why Not Just Use LaTeXML?

1. **Validation**: Tectonic/pdflatex catches LaTeX errors that LaTeXML might miss
2. **Package Verification**: Ensures all packages are installed before conversion
3. **Quality Check**: PDF output confirms the document compiles correctly
4. **Early Feedback**: Users get immediate feedback on LaTeX syntax errors

## Summary

**Tectonic** (implemented as pdflatex in the current setup) serves as:
- ✅ **Validation stage** - Checks LaTeX syntax before HTML conversion
- ✅ **PDF generator** - Creates PDF output for verification
- ✅ **Package validator** - Ensures all dependencies are available
- ✅ **Optional stage** - Pipeline can continue even if it fails

The stage is **non-critical** - if it fails, the conversion continues with LaTeXML-only, making the system more resilient.
