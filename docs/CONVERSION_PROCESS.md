# LaTeX to HTML Conversion Process

This document outlines the complete step-by-step process for converting LaTeX documents to HTML5.

## Overview

The conversion pipeline follows a multi-stage process:
1. **File Discovery & Extraction** - Extract and analyze the LaTeX project
2. **Tectonic Compilation** (Optional) - Compile LaTeX to PDF using Tectonic/pdflatex
3. **LaTeXML Conversion** - Convert LaTeX to HTML using LaTeXML library
4. **HTML Post-Processing** - Clean, optimize, and enhance the HTML output
5. **Validation** - Validate the final HTML output

---

## Detailed Process Steps

### Stage 0: Initial Setup & File Upload

1. **Receive Upload**
   - User uploads a ZIP file containing LaTeX project files
   - File is stored in `/app/uploads/{conversion_id}/`
   - Conversion ID is generated (UUID)

2. **Calculate Adaptive Timeout**
   - Analyze extracted directory size and file count
   - Calculate timeout based on:
     - Base timeout: 600 seconds (10 minutes)
     - File size: ~10 seconds per MB
     - File count: ~1 second per 10 files
     - Maximum: 14,400 seconds (4 hours) for files up to 100MB
   - Cache metadata for optimization

3. **Create Conversion Job**
   - Initialize `ConversionJob` with:
     - Job ID (UUID)
     - Input file path
     - Output directory path
     - Conversion options
     - Metadata (timeout, project structure, etc.)

---

### Stage 1: File Discovery & Extraction

**Service:** `FileDiscoveryService`

1. **Extract ZIP Archive**
   - Extract ZIP file to temporary directory
   - Validate path depth (configurable `MAX_PATH_DEPTH`)
   - Normalize paths for OS compatibility
   - Preserve directory structure

2. **Discover LaTeX Files**
   - Use **Breadth-First Search (BFS)** to find all `.tex` files
   - Identify main `.tex` file (usually `main.tex`, `document.tex`, or largest file)
   - Scan for supporting files:
     - `.cls` (document classes)
     - `.sty` (style files)
     - `.bib` (bibliography files)
     - `.bst` (bibliography styles)
     - Graphics files (`.pdf`, `.png`, `.jpg`, `.eps`, `.svg`)

3. **Parse LaTeX Dependencies**
   - Extract document class using regex: `\documentclass[...]{...}`
   - Extract packages using regex: `\usepackage[...]{...}`
   - Find `\input{...}` and `\include{...}` statements
   - Find `\bibliography{...}` references
   - Find `\graphicspath{...}` declarations
   - Find `\includegraphics{...}` references

4. **Build Project Structure**
   - Create `ProjectStructure` object containing:
     - Main `.tex` file path
     - All discovered `.tex` files
     - Supporting files by category
     - Dependency information
     - Project directory path

5. **Detect Custom Classes**
   - Use `LaTeXPreprocessor` to detect custom document classes
   - Search for `.cls` files using BFS
   - Store class file paths for LaTeXML

---

### Stage 2: Tectonic Compilation (Optional)

**Service:** `PDFLaTeXService` (uses `pdflatex`)

**Note:** This stage is optional. If it fails, the pipeline continues with LaTeXML-only conversion.

1. **Install Missing Packages**
   - Use `PackageManagerService` to detect missing LaTeX packages
   - Attempt to install packages using `tlmgr` (TeX Live Manager)
   - Log failed packages (may not be critical)

2. **Compile LaTeX to PDF**
   - Run `pdflatex` command:
     ```bash
     pdflatex --no-shell-escape --halt-on-error \
       --interaction=nonstopmode \
       -output-directory {output_dir} \
       {main_tex_file}
     ```
   - Output PDF saved to `{output_dir}/tectonic/`

3. **Handle Compilation Failure**
   - If compilation fails:
     - Log error details
     - Mark stage as `SKIPPED`
     - Continue to LaTeXML stage (fallback)
     - Validate LaTeX syntax before continuing

4. **Validate LaTeX Syntax** (if Tectonic fails)
   - Basic syntax validation
   - Check for common errors
   - Log warnings/errors
   - Continue to LaTeXML even if validation fails (with warnings)

---

### Stage 3: LaTeXML Conversion

**Service:** `LaTeXMLService` (uses `latexmlc` - Perl-based LaTeXML compiler)

This is the **core conversion stage** that converts LaTeX to HTML.

1. **Prepare LaTeXML Command**
   - Build command with options:
     ```bash
     latexmlc \
       --destination {output_html} \
       --nocomments \
       --parallel \
       --cache \
       --nodefaultresources \
       --timestamp=0 \
       --preload amsmath \
       --preload amssymb \
       --preload graphicx \
       --preload overpic \
       {main_tex_file} \
       --path {project_dir} \
       --path {parent_dirs} \
       --path /app
     ```

2. **Configure Search Paths**
   - Add project directory to search path
   - Add parent directories (up to 5 levels) recursively
   - Add discovered subdirectories (up to `MAX_PATH_DEPTH`)
   - Normalize all paths for OS compatibility

3. **Execute LaTeXML**
   - Run `latexmlc` process with timeout (70% of total job timeout)
   - Monitor process for completion or timeout
   - Capture stdout/stderr for error reporting

4. **LaTeXML Processing** (What happens inside LaTeXML)
   - **Parse LaTeX**: LaTeXML parses the LaTeX source code
   - **Resolve Dependencies**: Finds and loads all required packages and classes
   - **Build Document Tree**: Constructs an internal XML representation
   - **Convert to XML**: Transforms LaTeX commands to XML elements
   - **Generate HTML**: Converts XML to HTML5 with MathML for equations
   - **Handle Graphics**: Processes `\includegraphics` commands
   - **Process Bibliography**: Handles `\bibliography` and `\cite` commands

5. **Output**
   - HTML file saved to `{output_dir}/latexml/{main_file}.html`
   - May include:
     - MathML for mathematical equations
     - Embedded or linked graphics
     - Bibliography references
     - Cross-references

**Time Complexity:**
- Small files (< 1MB): 1-5 minutes
- Medium files (1-10MB): 5-15 minutes
- Large files (10-50MB): 15-60 minutes
- Very large files (50-100MB): 1-4 hours

---

### Stage 4: HTML Post-Processing

**Service:** `HTMLPostProcessor`

1. **Load HTML**
   - Read HTML file generated by LaTeXML
   - Parse with BeautifulSoup4 (lxml parser)

2. **Clean HTML Structure**
   - Remove unnecessary whitespace
   - Normalize HTML structure
   - Fix malformed tags
   - Remove empty elements

3. **Process Images/Graphics**
   - **If `skip_images` option is False:**
     - Find all image references
     - Convert PDF images to PNG using `dvisvgm` or `pdftoppm`
     - Convert EPS/PS to SVG
     - Optimize image formats
     - Update image paths in HTML
   - **If `skip_images` option is True:**
     - Skip all image conversion
     - Leave image references as-is

4. **Optimize MathML**
   - Optimize MathML equations
   - Ensure proper MathML namespace
   - Validate MathML structure

5. **Enhance HTML**
   - Add proper HTML5 doctype
   - Add meta tags (charset, viewport)
   - Add CSS for better rendering
   - Add JavaScript for interactivity (if needed)
   - Improve accessibility (ARIA labels, semantic HTML)

6. **SVG Optimization** (if applicable)
   - Optimize SVG files using `SVGOptimizer`
   - Remove unnecessary metadata
   - Compress SVG code

7. **Save Final HTML**
   - Write cleaned HTML to `{output_dir}/final.html`
   - Preserve original LaTeXML output in `{output_dir}/latexml/`

---

### Stage 5: Validation

**Service:** `HTMLValidator`

1. **Validate HTML Structure**
   - Check HTML5 validity
   - Validate MathML syntax
   - Check for broken links
   - Verify image references

2. **Check Completeness**
   - Ensure all required files are present
   - Verify output directory structure
   - Check for missing dependencies

3. **Generate Report**
   - Create validation report
   - Log warnings and errors
   - Store in job metadata

---

### Final: Result Packaging

1. **Create Output ZIP**
   - Package final HTML file
   - Include supporting files (images, CSS, etc.)
   - Create ZIP archive: `{output_dir}/{conversion_id}.zip`

2. **Update Job Status**
   - Mark job as `COMPLETED`
   - Store completion timestamp
   - Calculate total duration

3. **Cleanup** (background process)
   - Clean up temporary files after retention period
   - Remove old conversion data
   - Free up disk space

---

## Libraries & Tools Used

### Core Libraries

1. **LaTeXML** (`latexmlc`)
   - **Purpose**: Converts LaTeX to HTML/XML
   - **Language**: Perl
   - **What it does**:
     - Parses LaTeX source code
     - Resolves package dependencies
     - Converts LaTeX commands to XML/HTML
     - Generates MathML for equations
     - Handles graphics and bibliography

2. **Tectonic/pdflatex**
   - **Purpose**: Compiles LaTeX to PDF (optional)
   - **Language**: C/Rust (Tectonic) or C (pdflatex)
   - **What it does**:
     - Validates LaTeX syntax
     - Compiles document to PDF
     - Used for validation and fallback

3. **BeautifulSoup4** (Python)
   - **Purpose**: HTML parsing and manipulation
   - **Parser**: lxml
   - **What it does**:
     - Parses HTML structure
     - Modifies HTML elements
     - Cleans and optimizes HTML

4. **dvisvgm** / **pdftoppm**
   - **Purpose**: Image conversion
   - **What it does**:
     - Converts PDF to SVG/PNG
     - Converts EPS/PS to SVG
     - Optimizes image formats

### Supporting Services

- **FileDiscoveryService**: Extracts and analyzes LaTeX projects
- **LaTeXPreprocessor**: Detects custom classes and dependencies
- **PackageManagerService**: Installs missing LaTeX packages
- **AssetConversionService**: Converts images and graphics
- **HTMLValidator**: Validates final HTML output

---

## Error Handling & Fallbacks

1. **Tectonic Failure**
   - Falls back to LaTeXML-only conversion
   - Validates LaTeX syntax before continuing
   - Logs error details for debugging

2. **LaTeXML Timeout**
   - Adaptive timeout based on file size
   - Can be extended up to 4 hours for very large files
   - Provides detailed diagnostics on timeout

3. **Missing Packages**
   - Attempts to install via `tlmgr`
   - Continues if installation fails (may not be critical)
   - Logs failed packages for user review

4. **Image Conversion Failure**
   - Can skip images if `skip_images` option is enabled
   - Leaves original image references if conversion fails
   - Logs conversion errors

---

## Performance Characteristics

### Time Complexity by File Size

| File Size | Estimated Time | Primary Bottleneck |
|-----------|---------------|---------------------|
| < 1 MB    | 1-5 minutes   | LaTeXML parsing    |
| 1-10 MB   | 5-15 minutes  | LaTeXML processing |
| 10-50 MB  | 15-60 minutes | LaTeXML + dependencies |
| 50-100 MB | 1-4 hours     | LaTeXML + large dependency resolution |

### Resource Usage

- **CPU**: High during LaTeXML conversion (80-95% CPU usage)
- **Memory**: Moderate (2-5% for typical files, up to 10% for large files)
- **Disk**: Temporary storage for extracted files and intermediate outputs

---

## Configuration Options

### Conversion Options

- `max_processing_time`: Maximum time for entire conversion (seconds)
- `tectonic_options`: Options for Tectonic compilation
- `latexml_options`: Options for LaTeXML conversion
- `post_processing_options`:
  - `skip_images`: Skip image conversion (faster, smaller output)

### Path Configuration

- `MAX_PATH_DEPTH`: Maximum directory depth to search (default: unlimited)
- `MAX_PATH_LENGTH`: Maximum path length (default: 4096)
- `ENABLE_PATH_CACHING`: Enable path discovery caching (default: true)

---

## Progress Reporting

Progress is calculated based on:

1. **Completed Stages**: Base progress from completed stages (25% per stage)
2. **Current Stage Progress**: Estimated progress within current stage
   - Based on elapsed time vs. expected duration
   - Fallback calculation if stage timing unavailable
3. **Progressive Minimum**: Ensures visible progress over time
   - 1% after 30 seconds
   - 2% after 2 minutes
   - 3% after 5 minutes
   - 4% after 10 minutes

---

## Example Conversion Flow

```
1. Upload ZIP file (eLife-VOR-RA-2024-105138.zip)
   ↓
2. Extract to /app/uploads/{id}/extracted/
   ↓
3. Discover files: finalmanuscript.tex, elife.cls, figures/, etc.
   ↓
4. Try Tectonic compilation → FAILS (expected)
   ↓
5. Fall back to LaTeXML-only
   ↓
6. Run LaTeXML conversion (takes 15-30 minutes for large files)
   - Parse LaTeX
   - Resolve dependencies
   - Convert to HTML
   ↓
7. Post-process HTML
   - Clean structure
   - Skip images (if option enabled)
   - Optimize output
   ↓
8. Validate HTML
   ↓
9. Package as ZIP
   ↓
10. Return conversion result
```

---

## Notes

- All conversions run in Docker containers with isolated environments
- Jobs are tracked in memory (lost on restart)
- Output files are retained for configurable period (default: 24 hours)
- Concurrent conversions are limited (default: 5 concurrent jobs)
- Timeouts are adaptive based on file size and complexity
