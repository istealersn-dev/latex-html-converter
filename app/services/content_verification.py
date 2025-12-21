"""
Content verification service for LaTeX → HTML conversion.

This service analyzes both source LaTeX and output HTML to verify content preservation
and detect any content loss during conversion.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class LatexContentMetrics:
    """Metrics extracted from LaTeX source."""

    sections: int = 0
    subsections: int = 0
    subsubsections: int = 0
    figures: int = 0
    tables: int = 0
    equations: int = 0
    inline_math: int = 0
    citations: int = 0
    references: int = 0
    bibliography_entries: int = 0
    word_count: int = 0
    tikz_diagrams: int = 0
    custom_commands: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)


@dataclass
class HtmlContentMetrics:
    """Metrics extracted from HTML output."""

    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    figures: int = 0
    images: int = 0
    tables: int = 0
    math_elements: int = 0
    inline_math: int = 0
    citations: int = 0
    links: int = 0
    word_count: int = 0
    svg_diagrams: int = 0


@dataclass
class ContentPreservationReport:
    """Detailed report on content preservation."""

    latex_metrics: LatexContentMetrics
    html_metrics: HtmlContentMetrics
    preservation_score: float  # 0-100
    sections_preserved: float  # Percentage
    figures_preserved: float  # Percentage
    tables_preserved: float  # Percentage
    equations_preserved: float  # Percentage
    citations_preserved: float  # Percentage
    word_count_preserved: float  # Percentage
    missing_content: list[str] = field(default_factory=list)
    altered_content: list[str] = field(default_factory=list)
    quality_assessment: str = ""  # "excellent", "good", "fair", "poor"


class ContentVerificationService:
    """Service to verify content preservation during LaTeX → HTML conversion."""

    def __init__(self):
        """Initialize the content verification service."""
        # LaTeX patterns for content detection
        self.section_pattern = re.compile(r"\\section\{([^}]+)\}")
        self.subsection_pattern = re.compile(r"\\subsection\{([^}]+)\}")
        self.subsubsection_pattern = re.compile(r"\\subsubsection\{([^}]+)\}")
        self.figure_pattern = re.compile(r"\\begin\{figure\}.*?\\end\{figure\}", re.DOTALL)
        self.table_pattern = re.compile(r"\\begin\{table\}.*?\\end\{table\}", re.DOTALL)
        self.equation_pattern = re.compile(
            r"\\begin\{(equation|align|gather|multline)\}.*?\\end\{\1\}", re.DOTALL
        )
        self.inline_math_pattern = re.compile(r"\$[^$]+\$|\\\([^)]+\\\)")
        self.citation_pattern = re.compile(r"\\cite\{[^}]+\}")
        self.reference_pattern = re.compile(r"\\ref\{[^}]+\}|\\eqref\{[^}]+\}")
        self.tikz_pattern = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.DOTALL)
        self.bibitem_pattern = re.compile(r"\\bibitem\{[^}]+\}")
        self.package_pattern = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
        self.newcommand_pattern = re.compile(r"\\newcommand\{\\([^}]+)\}")

        logger.info("Content verification service initialized")

    def analyze_latex_content(self, latex_file: Path) -> LatexContentMetrics:
        """
        Analyze LaTeX source file and extract content metrics.

        Args:
            latex_file: Path to LaTeX source file

        Returns:
            LatexContentMetrics with all detected content
        """
        try:
            with open(latex_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            metrics = LatexContentMetrics()

            # Count structural elements
            metrics.sections = len(self.section_pattern.findall(content))
            metrics.subsections = len(self.subsection_pattern.findall(content))
            metrics.subsubsections = len(self.subsubsection_pattern.findall(content))

            # Count figures and tables
            metrics.figures = len(self.figure_pattern.findall(content))
            metrics.tables = len(self.table_pattern.findall(content))

            # Count equations
            metrics.equations = len(self.equation_pattern.findall(content))
            metrics.inline_math = len(self.inline_math_pattern.findall(content))

            # Count citations and references
            metrics.citations = len(self.citation_pattern.findall(content))
            metrics.references = len(self.reference_pattern.findall(content))
            metrics.bibliography_entries = len(self.bibitem_pattern.findall(content))

            # Count TikZ diagrams
            metrics.tikz_diagrams = len(self.tikz_pattern.findall(content))

            # Extract packages
            metrics.packages = list(set(self.package_pattern.findall(content)))

            # Extract custom commands
            metrics.custom_commands = list(set(self.newcommand_pattern.findall(content)))

            # Approximate word count (exclude LaTeX commands)
            # Remove comments
            content_no_comments = re.sub(r"%.*", "", content)
            # Remove commands
            content_no_commands = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})*", " ", content_no_comments)
            # Remove inline math
            content_no_math = re.sub(r"\$[^$]*\$", " ", content_no_commands)
            # Count words
            words = content_no_math.split()
            metrics.word_count = len([w for w in words if len(w) > 0])

            logger.info(
                f"LaTeX analysis complete: {metrics.sections} sections, "
                f"{metrics.figures} figures, {metrics.equations} equations, "
                f"{metrics.word_count} words"
            )

            return metrics

        except Exception as exc:
            logger.error(f"Failed to analyze LaTeX content: {exc}")
            return LatexContentMetrics()

    def analyze_html_content(self, html_file: Path) -> HtmlContentMetrics:
        """
        Analyze HTML output file and extract content metrics.

        Args:
            html_file: Path to HTML output file

        Returns:
            HtmlContentMetrics with all detected content
        """
        try:
            with open(html_file, encoding="utf-8") as f:
                content = f.read()

            try:
                import lxml
                soup = BeautifulSoup(content, "lxml")
            except ImportError:
                soup = BeautifulSoup(content, "html.parser")
            metrics = HtmlContentMetrics()

            # Count headings
            metrics.h1_count = len(soup.find_all("h1"))
            metrics.h2_count = len(soup.find_all("h2"))
            metrics.h3_count = len(soup.find_all("h3"))
            metrics.h4_count = len(soup.find_all("h4"))
            metrics.h5_count = len(soup.find_all("h5"))
            metrics.h6_count = len(soup.find_all("h6"))

            # Count figures and images
            metrics.figures = len(soup.find_all("figure"))
            metrics.images = len(soup.find_all("img"))

            # Count tables
            metrics.tables = len(soup.find_all("table"))

            # Count math elements
            # MathML elements
            math_elements = soup.find_all("math")
            # MathJax elements
            mathjax_display = soup.find_all("div", class_=re.compile(r"math|equation"))
            mathjax_inline = soup.find_all("span", class_=re.compile(r"math"))
            # LaTeXML math elements
            ltx_math = soup.find_all(class_=re.compile(r"ltx_Math|ltx_equation"))

            metrics.math_elements = len(math_elements) + len(mathjax_display) + len(ltx_math)
            metrics.inline_math = len(mathjax_inline)

            # Count citations
            metrics.citations = len(soup.find_all("cite"))

            # Count links
            metrics.links = len(soup.find_all("a"))

            # Count SVG diagrams (converted from TikZ/PDF)
            metrics.svg_diagrams = len([img for img in soup.find_all("img") if img.get("src", "").endswith(".svg")])

            # Word count (exclude scripts, styles, conversion warnings)
            for tag in soup(["script", "style", "head"]):
                tag.decompose()
            # Remove conversion warnings summary
            for warning in soup.find_all(class_=re.compile(r"conversion-warning|conversion-summary")):
                warning.decompose()

            text = soup.get_text(separator=" ", strip=True)
            words = text.split()
            metrics.word_count = len([w for w in words if len(w) > 0])

            logger.info(
                f"HTML analysis complete: {metrics.h1_count + metrics.h2_count + metrics.h3_count} headings, "
                f"{metrics.figures + metrics.images} figures, {metrics.math_elements} equations, "
                f"{metrics.word_count} words"
            )

            return metrics

        except Exception as exc:
            logger.error(f"Failed to analyze HTML content: {exc}")
            return HtmlContentMetrics()

    def verify_content_preservation(
        self, latex_file: Path, html_file: Path
    ) -> ContentPreservationReport:
        """
        Compare LaTeX source and HTML output to verify content preservation.

        Args:
            latex_file: Path to LaTeX source file
            html_file: Path to HTML output file

        Returns:
            ContentPreservationReport with detailed analysis
        """
        logger.info(f"Verifying content preservation: {latex_file} -> {html_file}")

        # Analyze both files
        latex_metrics = self.analyze_latex_content(latex_file)
        html_metrics = self.analyze_html_content(html_file)

        # Calculate preservation percentages
        sections_preserved = self._calculate_preservation_percentage(
            latex_metrics.sections + latex_metrics.subsections + latex_metrics.subsubsections,
            html_metrics.h1_count
            + html_metrics.h2_count
            + html_metrics.h3_count
            + html_metrics.h4_count
            + html_metrics.h5_count
            + html_metrics.h6_count,
        )

        figures_preserved = self._calculate_preservation_percentage(
            latex_metrics.figures, html_metrics.figures + html_metrics.images
        )

        tables_preserved = self._calculate_preservation_percentage(
            latex_metrics.tables, html_metrics.tables
        )

        equations_preserved = self._calculate_preservation_percentage(
            latex_metrics.equations, html_metrics.math_elements
        )

        citations_preserved = self._calculate_preservation_percentage(
            latex_metrics.citations, html_metrics.citations
        )

        word_count_preserved = self._calculate_preservation_percentage(
            latex_metrics.word_count, html_metrics.word_count, tolerance=0.15
        )

        # Identify missing content
        missing_content = self._identify_missing_content(
            latex_metrics,
            html_metrics,
            sections_preserved,
            figures_preserved,
            tables_preserved,
            equations_preserved,
            citations_preserved,
        )

        # Identify altered content
        altered_content = self._identify_altered_content(latex_metrics, html_metrics, word_count_preserved)

        # Calculate overall preservation score (weighted average)
        preservation_score = self._calculate_overall_score(
            sections_preserved,
            figures_preserved,
            tables_preserved,
            equations_preserved,
            citations_preserved,
            word_count_preserved,
        )

        # Quality assessment
        quality_assessment = self._assess_quality(preservation_score)

        report = ContentPreservationReport(
            latex_metrics=latex_metrics,
            html_metrics=html_metrics,
            preservation_score=preservation_score,
            sections_preserved=sections_preserved,
            figures_preserved=figures_preserved,
            tables_preserved=tables_preserved,
            equations_preserved=equations_preserved,
            citations_preserved=citations_preserved,
            word_count_preserved=word_count_preserved,
            missing_content=missing_content,
            altered_content=altered_content,
            quality_assessment=quality_assessment,
        )

        logger.info(
            f"Content verification complete: {preservation_score:.1f}% preserved ({quality_assessment})"
        )

        return report

    def _calculate_preservation_percentage(
        self, source_count: int, output_count: int, tolerance: float = 0.0
    ) -> float:
        """
        Calculate preservation percentage with optional tolerance.

        Args:
            source_count: Count in source LaTeX
            output_count: Count in output HTML
            tolerance: Acceptable relative difference (0.0-1.0)

        Returns:
            Preservation percentage (0-100)
        """
        if source_count == 0:
            # If source is empty but output has content, this indicates extra content was added
            # Return 0% preservation to indicate this is not a preservation success
            return 0.0 if output_count > 0 else 100.0  # 100% only if both are empty

        if output_count >= source_count:
            return 100.0

        # Calculate percentage
        percentage = (output_count / source_count) * 100

        # Apply tolerance (e.g., 90% word count is still 100% preservation within 15% tolerance)
        if tolerance > 0:
            lower_bound = source_count * (1 - tolerance)
            if output_count >= lower_bound:
                return 100.0

        return min(100.0, percentage)

    def _identify_missing_content(
        self,
        latex: LatexContentMetrics,
        html: HtmlContentMetrics,
        sections_preserved: float,
        figures_preserved: float,
        tables_preserved: float,
        equations_preserved: float,
        citations_preserved: float,
    ) -> list[str]:
        """Identify types of missing content."""
        missing = []

        total_sections = latex.sections + latex.subsections + latex.subsubsections
        total_headings = (
            html.h1_count + html.h2_count + html.h3_count + html.h4_count + html.h5_count + html.h6_count
        )

        if sections_preserved < 100.0:
            missing_count = total_sections - total_headings
            missing.append(f"{missing_count} section(s)/heading(s)")

        if figures_preserved < 100.0:
            missing_count = latex.figures - (html.figures + html.images)
            missing.append(f"{missing_count} figure(s)")

        if tables_preserved < 100.0:
            missing_count = latex.tables - html.tables
            missing.append(f"{missing_count} table(s)")

        if equations_preserved < 100.0:
            missing_count = latex.equations - html.math_elements
            missing.append(f"{missing_count} equation(s)")

        if citations_preserved < 100.0:
            missing_count = latex.citations - html.citations
            missing.append(f"{missing_count} citation(s)")

        if latex.tikz_diagrams > 0:
            tikz_preserved = html.svg_diagrams
            if tikz_preserved < latex.tikz_diagrams:
                missing_count = latex.tikz_diagrams - tikz_preserved
                missing.append(f"{missing_count} TikZ diagram(s)")

        return missing

    def _identify_altered_content(
        self, latex: LatexContentMetrics, html: HtmlContentMetrics, word_count_preserved: float
    ) -> list[str]:
        """Identify types of altered content."""
        altered = []

        if word_count_preserved < 90.0:
            diff_percentage = abs(100 - word_count_preserved)
            altered.append(f"Word count differs by {diff_percentage:.1f}%")

        # Check if extra content was added
        total_sections = latex.sections + latex.subsections + latex.subsubsections
        total_headings = (
            html.h1_count + html.h2_count + html.h3_count + html.h4_count + html.h5_count + html.h6_count
        )

        if total_headings > total_sections:
            extra_count = total_headings - total_sections
            altered.append(f"{extra_count} extra heading(s) added")

        return altered

    def _calculate_overall_score(
        self,
        sections: float,
        figures: float,
        tables: float,
        equations: float,
        citations: float,
        words: float,
    ) -> float:
        """
        Calculate weighted overall preservation score.

        Weights:
        - Sections: 20%
        - Figures: 15%
        - Tables: 10%
        - Equations: 15%
        - Citations: 10%
        - Word count: 30%
        """
        weights = {
            "sections": 0.20,
            "figures": 0.15,
            "tables": 0.10,
            "equations": 0.15,
            "citations": 0.10,
            "words": 0.30,
        }

        score = (
            sections * weights["sections"]
            + figures * weights["figures"]
            + tables * weights["tables"]
            + equations * weights["equations"]
            + citations * weights["citations"]
            + words * weights["words"]
        )

        return round(score, 2)

    def _assess_quality(self, score: float) -> str:
        """Assess conversion quality based on preservation score."""
        if score >= 95.0:
            return "excellent"
        elif score >= 85.0:
            return "good"
        elif score >= 70.0:
            return "fair"
        else:
            return "poor"

    def generate_verification_summary(self, report: ContentPreservationReport) -> dict[str, Any]:
        """
        Generate a user-friendly summary of verification results.

        Args:
            report: ContentPreservationReport

        Returns:
            Dictionary with summary information
        """
        summary = {
            "overall_score": report.preservation_score,
            "quality": report.quality_assessment,
            "breakdown": {
                "sections": {
                    "source": (
                        report.latex_metrics.sections
                        + report.latex_metrics.subsections
                        + report.latex_metrics.subsubsections
                    ),
                    "output": (
                        report.html_metrics.h1_count
                        + report.html_metrics.h2_count
                        + report.html_metrics.h3_count
                        + report.html_metrics.h4_count
                        + report.html_metrics.h5_count
                        + report.html_metrics.h6_count
                    ),
                    "preserved": f"{report.sections_preserved:.1f}%",
                },
                "figures": {
                    "source": report.latex_metrics.figures,
                    "output": report.html_metrics.figures + report.html_metrics.images,
                    "preserved": f"{report.figures_preserved:.1f}%",
                },
                "tables": {
                    "source": report.latex_metrics.tables,
                    "output": report.html_metrics.tables,
                    "preserved": f"{report.tables_preserved:.1f}%",
                },
                "equations": {
                    "source": report.latex_metrics.equations,
                    "output": report.html_metrics.math_elements,
                    "preserved": f"{report.equations_preserved:.1f}%",
                },
                "citations": {
                    "source": report.latex_metrics.citations,
                    "output": report.html_metrics.citations,
                    "preserved": f"{report.citations_preserved:.1f}%",
                },
                "words": {
                    "source": report.latex_metrics.word_count,
                    "output": report.html_metrics.word_count,
                    "preserved": f"{report.word_count_preserved:.1f}%",
                },
            },
            "missing_content": report.missing_content,
            "altered_content": report.altered_content,
        }

        return summary
