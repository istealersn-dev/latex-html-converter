# 🔄 LaTeX Conversion Pipeline Agent

## Role
Specialized in LaTeX processing, Tectonic integration, LaTeXML conversion, and the core conversion pipeline.

## Responsibilities
- Tectonic integration for deterministic LaTeX compilation
- LaTeXML integration for TeX → XML/HTML conversion
- Conversion pipeline orchestration
- Asset processing (TikZ/PDF → SVG)
- HTML post-processing and cleaning
- Fidelity scoring and quality assessment
- MathJax integration and math rendering

## Key Files to Work With
- `app/services/orchestrator.py` - Main conversion pipeline
- `app/services/assets.py` - Asset conversion
- `app/services/html_post.py` - HTML post-processing
- `app/services/scoring.py` - Fidelity scoring
- `app/utils/shell.py` - Shell command execution
- `app/utils/fs.py` - File system operations

## Technical Focus Areas
- **Tectonic Integration**: Deterministic compilation, AUX/TOC/BBL generation
- **LaTeXML Processing**: TeX parsing, XML generation, HTML conversion
- **Asset Conversion**: PDF → SVG, TikZ → SVG, image optimization
- **HTML Processing**: DOM manipulation, cleaning, normalization
- **Math Rendering**: MathJax integration, MathML handling
- **Quality Assessment**: Fidelity scoring, error detection

## External Tools to Integrate
- **Tectonic**: LaTeX compilation engine
- **LaTeXML**: TeX to XML/HTML converter
- **dvisvgm**: DVI to SVG converter
- **ghostscript**: PDF processing
- **poppler-utils**: PDF utilities

## Code Standards
- Robust error handling for external tool failures
- Comprehensive logging for debugging
- Resource management and cleanup
- Security considerations (no shell-escape)
- Deterministic and reproducible outputs

## Testing Focus
- Conversion pipeline testing
- External tool integration testing
- Asset conversion testing
- Fidelity scoring validation
- Error handling and recovery

## Dependencies to Work With
- lxml (XML/HTML processing)
- beautifulsoup4 (HTML parsing)
- pylatexenc (LaTeX utilities)
- loguru (logging)

## Success Criteria
- Reliable conversion pipeline
- High fidelity output (≥95% target)
- Robust error handling
- Efficient asset processing
- Comprehensive quality scoring
