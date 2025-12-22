"""
Content diff report service for LaTeX → HTML conversion.

This service generates detailed, section-by-section comparison reports showing
exactly what content was preserved, altered, or lost during conversion.
"""

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class ContentSection:
    """Represents a section of content (LaTeX or HTML)."""

    title: str
    level: int  # 1=section, 2=subsection, 3=subsubsection
    content: str
    figures: list[str] = field(default_factory=list)
    tables: int = 0
    equations: int = 0
    citations: int = 0
    word_count: int = 0
    line_start: int = 0
    line_end: int = 0


@dataclass
class SectionDiff:
    """Represents differences in a section."""

    title: str
    level: int
    source_section: ContentSection | None
    output_section: ContentSection | None
    preservation_score: float  # 0-100
    status: str  # "preserved", "altered", "missing", "added"
    differences: list[str] = field(default_factory=list)
    confidence: str = "high"  # "high", "medium", "low"


@dataclass
class ContentDiffReport:
    """Complete diff report for conversion."""

    source_file: str
    output_file: str
    overall_preservation: float
    section_diffs: list[SectionDiff] = field(default_factory=list)
    global_differences: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class ContentDiffReportService:
    """Service to generate detailed content diff reports."""

    def __init__(self):
        """Initialize the content diff report service."""
        # LaTeX patterns
        self.section_pattern = re.compile(
            r"\\section\*?\{([^}]+)\}(.*?)(?=\\(?:section|subsection|subsubsection|end\{document\}|\Z))",
            re.DOTALL,
        )
        self.subsection_pattern = re.compile(
            r"\\subsection\*?\{([^}]+)\}(.*?)(?=\\(?:section|subsection|subsubsection|end\{document\}|\Z))",
            re.DOTALL,
        )
        self.subsubsection_pattern = re.compile(
            r"\\subsubsection\*?\{([^}]+)\}(.*?)(?=\\(?:section|subsection|subsubsection|end\{document\}|\Z))",
            re.DOTALL,
        )

        # Content patterns
        self.figure_pattern = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
        self.table_pattern = re.compile(r"\\begin\{table\}.*?\\end\{table\}", re.DOTALL)
        self.equation_pattern = re.compile(
            r"\\begin\{(?:equation|align|gather|multline)\}.*?\\end\{(?:equation|align|gather|multline)\}",
            re.DOTALL,
        )
        self.citation_pattern = re.compile(r"\\cite\{[^}]+\}")

        logger.info("Content diff report service initialized")

    def generate_diff_report(
        self, latex_file: Path, html_file: Path
    ) -> ContentDiffReport:
        """
        Generate a detailed diff report comparing LaTeX source and HTML output.

        Args:
            latex_file: Path to LaTeX source file
            html_file: Path to HTML output file

        Returns:
            ContentDiffReport with detailed comparison
        """
        logger.info(f"Generating diff report: {latex_file} -> {html_file}")

        # Extract structured content from both files
        latex_sections = self._extract_latex_sections(latex_file)
        html_sections = self._extract_html_sections(html_file)

        # Compare sections
        section_diffs = self._compare_sections(latex_sections, html_sections)

        # Calculate overall preservation
        total_score = sum(diff.preservation_score for diff in section_diffs)
        overall_preservation = (
            total_score / len(section_diffs) if section_diffs else 100.0
        )

        # Identify global differences
        global_diffs = self._identify_global_differences(
            latex_sections, html_sections
        )

        # Generate summary
        summary = self._generate_summary(section_diffs, overall_preservation)

        report = ContentDiffReport(
            source_file=str(latex_file),
            output_file=str(html_file),
            overall_preservation=overall_preservation,
            section_diffs=section_diffs,
            global_differences=global_diffs,
            summary=summary,
        )

        logger.info(
            f"Diff report generated: {overall_preservation:.1f}% preservation across {len(section_diffs)} sections"
        )

        return report

    def _extract_latex_sections(self, latex_file: Path) -> list[ContentSection]:
        """Extract sections from LaTeX source."""
        try:
            with open(latex_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            sections = []

            # Find all sections with hierarchical structure
            # Pattern: \section{Title}content...
            section_matches = list(
                re.finditer(
                    r"\\(section|subsection|subsubsection)\*?\{([^}]+)\}",
                    content,
                )
            )

            for i, match in enumerate(section_matches):
                section_type = match.group(1)
                title = match.group(2)
                start_pos = match.end()

                # Find end position (next section or end of document)
                if i + 1 < len(section_matches):
                    end_pos = section_matches[i + 1].start()
                else:
                    # Find \end{document} or end of file
                    end_match = re.search(r"\\end\{document\}", content[start_pos:])
                    end_pos = (
                        start_pos + end_match.start()
                        if end_match
                        else len(content)
                    )

                section_content = content[start_pos:end_pos]

                # Determine level
                level = 1 if section_type == "section" else (
                    2 if section_type == "subsection" else 3
                )

                # Extract content elements
                figures = self.figure_pattern.findall(section_content)
                tables = len(self.table_pattern.findall(section_content))
                equations = len(self.equation_pattern.findall(section_content))
                citations = len(self.citation_pattern.findall(section_content))

                # Word count (approximate)
                # Improved regex to match LaTeX commands more accurately:
                # - Matches \command, \command[], \command{}, \command[]{}, etc.
                # - Handles nested braces and brackets
                clean_content = re.sub(r"\\[a-zA-Z@]+(\[[^\]]*\])*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*", " ", section_content)
                clean_content = re.sub(r"\$[^$]*\$", " ", clean_content)
                words = clean_content.split()
                word_count = len([w for w in words if len(w) > 0])

                section = ContentSection(
                    title=title,
                    level=level,
                    content=section_content[:500],  # Store preview
                    figures=figures,
                    tables=tables,
                    equations=equations,
                    citations=citations,
                    word_count=word_count,
                    line_start=content[:match.start()].count("\n") + 1,
                    line_end=content[:end_pos].count("\n") + 1,
                )

                sections.append(section)

            logger.info(f"Extracted {len(sections)} sections from LaTeX")
            return sections

        except Exception as exc:
            logger.error(f"Failed to extract LaTeX sections: {exc}")
            return []

    def _extract_html_sections(self, html_file: Path) -> list[ContentSection]:
        """Extract sections from HTML output."""
        try:
            with open(html_file, encoding="utf-8") as f:
                content = f.read()

            try:
                import lxml
                soup = BeautifulSoup(content, "lxml")
            except ImportError:
                soup = BeautifulSoup(content, "html.parser")
            sections = []

            # Find all heading tags (h1-h6)
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

            for heading in headings:
                title = heading.get_text(strip=True)
                level = int(heading.name[1])  # Extract number from h1, h2, etc.

                # Get content between this heading and the next
                section_content = []
                for sibling in heading.find_next_siblings():
                    if sibling.name and sibling.name.startswith("h") and sibling.name[1].isdigit():
                        # Found next heading
                        break
                    section_content.append(sibling)

                # Analyze section content
                figures = []
                tables = 0
                equations = 0
                citations = 0

                for elem in section_content:
                    # Count figures/images
                    figures.extend([
                        img.get("src", "") for img in elem.find_all("img")
                    ])

                    # Count tables
                    tables += len(elem.find_all("table"))

                    # Count equations (multiple formats)
                    equations += len(elem.find_all("math"))
                    equations += len(elem.find_all(class_=re.compile(r"math|equation")))

                    # Count citations
                    citations += len(elem.find_all("cite"))

                # Word count
                text = " ".join(elem.get_text(strip=True) for elem in section_content)
                words = text.split()
                word_count = len([w for w in words if len(w) > 0])

                section = ContentSection(
                    title=title,
                    level=level,
                    content=text[:500],  # Store preview
                    figures=figures,
                    tables=tables,
                    equations=equations,
                    citations=citations,
                    word_count=word_count,
                )

                sections.append(section)

            logger.info(f"Extracted {len(sections)} sections from HTML")
            return sections

        except Exception as exc:
            logger.error(f"Failed to extract HTML sections: {exc}")
            return []

    def _compare_sections(
        self,
        latex_sections: list[ContentSection],
        html_sections: list[ContentSection],
    ) -> list[SectionDiff]:
        """Compare LaTeX and HTML sections to identify differences."""
        diffs = []

        # Match sections by title (fuzzy matching)
        matched_html = set()

        for latex_section in latex_sections:
            # Try to find matching HTML section
            html_match = None
            best_similarity = 0.0

            for i, html_section in enumerate(html_sections):
                if i in matched_html:
                    continue

                similarity = self._calculate_title_similarity(
                    latex_section.title, html_section.title
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    html_match = html_section
                    match_index = i

            if html_match and best_similarity > 0.6:
                # Found a match
                matched_html.add(match_index)
                diff = self._create_section_diff(latex_section, html_match)
            else:
                # No match - section is missing
                diff = SectionDiff(
                    title=latex_section.title,
                    level=latex_section.level,
                    source_section=latex_section,
                    output_section=None,
                    preservation_score=0.0,
                    status="missing",
                    differences=["Entire section missing from output"],
                    confidence="high",
                )

            diffs.append(diff)

        # Check for added sections in HTML (not in LaTeX)
        for i, html_section in enumerate(html_sections):
            if i not in matched_html:
                diff = SectionDiff(
                    title=html_section.title,
                    level=html_section.level,
                    source_section=None,
                    output_section=html_section,
                    preservation_score=0.0,
                    status="added",
                    differences=["Section added in output (not in source)"],
                    confidence="medium",
                )
                diffs.append(diff)

        return diffs

    def _create_section_diff(
        self, latex_section: ContentSection, html_section: ContentSection
    ) -> SectionDiff:
        """Create a diff for two matched sections."""
        differences = []
        scores = []

        # Compare figures
        if latex_section.figures:
            figure_preservation = (
                len(html_section.figures) / len(latex_section.figures)
            ) * 100
            scores.append(figure_preservation)
            if figure_preservation < 100:
                missing = len(latex_section.figures) - len(html_section.figures)
                differences.append(f"{missing} figure(s) missing")
        else:
            scores.append(100.0)

        # Compare tables
        if latex_section.tables > 0:
            table_preservation = (html_section.tables / latex_section.tables) * 100
            scores.append(table_preservation)
            if table_preservation < 100:
                missing = latex_section.tables - html_section.tables
                differences.append(f"{missing} table(s) missing")
        else:
            scores.append(100.0)

        # Compare equations
        if latex_section.equations > 0:
            equation_preservation = (
                html_section.equations / latex_section.equations
            ) * 100
            scores.append(equation_preservation)
            if equation_preservation < 100:
                missing = latex_section.equations - html_section.equations
                differences.append(f"{missing} equation(s) missing")
        else:
            scores.append(100.0)

        # Compare citations
        if latex_section.citations > 0:
            citation_preservation = (
                html_section.citations / latex_section.citations
            ) * 100
            scores.append(citation_preservation)
            if citation_preservation < 100:
                missing = latex_section.citations - html_section.citations
                differences.append(f"{missing} citation(s) missing")
        else:
            scores.append(100.0)

        # Compare word count
        if latex_section.word_count > 0:
            word_preservation = (
                html_section.word_count / latex_section.word_count
            ) * 100
            # Allow 15% tolerance for word count
            if abs(word_preservation - 100) <= 15:
                word_preservation = 100.0
            scores.append(word_preservation)
            if word_preservation < 95:
                diff_pct = abs(100 - word_preservation)
                differences.append(f"Word count differs by {diff_pct:.1f}%")
        else:
            scores.append(100.0)

        # Calculate overall preservation score
        preservation_score = sum(scores) / len(scores) if scores else 100.0

        # Determine status and confidence
        if preservation_score >= 95:
            status = "preserved"
            confidence = "high"
        elif preservation_score >= 70:
            status = "altered"
            confidence = "medium"
        else:
            status = "altered"
            confidence = "low"

        if not differences:
            differences = ["Content fully preserved"]

        return SectionDiff(
            title=latex_section.title,
            level=latex_section.level,
            source_section=latex_section,
            output_section=html_section,
            preservation_score=preservation_score,
            status=status,
            differences=differences,
            confidence=confidence,
        )

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two section titles."""
        # Simple similarity based on normalized text
        title1_norm = title1.lower().strip()
        title2_norm = title2.lower().strip()

        if title1_norm == title2_norm:
            return 1.0

        # Check if one contains the other
        if title1_norm in title2_norm or title2_norm in title1_norm:
            return 0.8

        # Word-based similarity
        words1 = set(title1_norm.split())
        words2 = set(title2_norm.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _identify_global_differences(
        self,
        latex_sections: list[ContentSection],
        html_sections: list[ContentSection],
    ) -> list[str]:
        """Identify global differences affecting the entire document."""
        diffs = []

        # Check section count
        if len(latex_sections) != len(html_sections):
            diff = len(latex_sections) - len(html_sections)
            if diff > 0:
                diffs.append(f"{diff} section(s) missing from output")
            else:
                diffs.append(f"{abs(diff)} extra section(s) in output")

        # Check total word count
        latex_words = sum(s.word_count for s in latex_sections)
        html_words = sum(s.word_count for s in html_sections)
        if latex_words > 0:
            word_diff_pct = abs((html_words / latex_words) * 100 - 100)
            if word_diff_pct > 15:
                diffs.append(f"Total word count differs by {word_diff_pct:.1f}%")

        # Check total figures
        latex_figs = sum(len(s.figures) for s in latex_sections)
        html_figs = sum(len(s.figures) for s in html_sections)
        if latex_figs != html_figs:
            diffs.append(
                f"Figure count: {latex_figs} (source) vs {html_figs} (output)"
            )

        return diffs

    def _generate_summary(
        self, section_diffs: list[SectionDiff], overall_preservation: float
    ) -> dict[str, Any]:
        """Generate summary statistics for the diff report."""
        preserved_count = sum(1 for d in section_diffs if d.status == "preserved")
        altered_count = sum(1 for d in section_diffs if d.status == "altered")
        missing_count = sum(1 for d in section_diffs if d.status == "missing")
        added_count = sum(1 for d in section_diffs if d.status == "added")

        high_confidence = sum(1 for d in section_diffs if d.confidence == "high")
        medium_confidence = sum(1 for d in section_diffs if d.confidence == "medium")
        low_confidence = sum(1 for d in section_diffs if d.confidence == "low")

        return {
            "total_sections": len(section_diffs),
            "preserved_sections": preserved_count,
            "altered_sections": altered_count,
            "missing_sections": missing_count,
            "added_sections": added_count,
            "overall_preservation": overall_preservation,
            "confidence_distribution": {
                "high": high_confidence,
                "medium": medium_confidence,
                "low": low_confidence,
            },
        }

    def export_report_json(self, report: ContentDiffReport, output_file: Path) -> None:
        """Export diff report as JSON file."""
        try:
            report_dict = {
                "source_file": report.source_file,
                "output_file": report.output_file,
                "overall_preservation": report.overall_preservation,
                "summary": report.summary,
                "global_differences": report.global_differences,
                "sections": [
                    {
                        "title": diff.title,
                        "level": diff.level,
                        "preservation_score": diff.preservation_score,
                        "status": diff.status,
                        "confidence": diff.confidence,
                        "differences": diff.differences,
                        "source": {
                            "figures": len(diff.source_section.figures) if diff.source_section else 0,
                            "tables": diff.source_section.tables if diff.source_section else 0,
                            "equations": diff.source_section.equations if diff.source_section else 0,
                            "citations": diff.source_section.citations if diff.source_section else 0,
                            "word_count": diff.source_section.word_count if diff.source_section else 0,
                        },
                        "output": {
                            "figures": len(diff.output_section.figures) if diff.output_section else 0,
                            "tables": diff.output_section.tables if diff.output_section else 0,
                            "equations": diff.output_section.equations if diff.output_section else 0,
                            "citations": diff.output_section.citations if diff.output_section else 0,
                            "word_count": diff.output_section.word_count if diff.output_section else 0,
                        },
                    }
                    for diff in report.section_diffs
                ],
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported diff report to JSON: {output_file}")

        except Exception as exc:
            logger.error(f"Failed to export JSON report: {exc}")
            raise

    def generate_html_report(self, report: ContentDiffReport, output_file: Path) -> None:
        """Generate a beautiful HTML diff report."""
        try:
            html_content = self._create_html_report_template(report)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info(f"Generated HTML diff report: {output_file}")

        except Exception as exc:
            logger.error(f"Failed to generate HTML report: {exc}")
            raise

    def _create_html_report_template(self, report: ContentDiffReport) -> str:
        """Create HTML template for diff report."""
        # Determine overall quality color
        score = report.overall_preservation
        if score >= 95:
            color = "#11998e"
        elif score >= 85:
            color = "#4facfe"
        elif score >= 70:
            color = "#fa709a"
        else:
            color = "#f5576c"

        # Generate sections HTML
        sections_html = ""
        for diff in report.section_diffs:
            sections_html += self._generate_section_html(diff)

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Content Diff Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            padding: 20px;
            color: #2c3e50;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, {color} 0%, {color}dd 100%);
            color: white;
            padding: 40px;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .score {{
            font-size: 3em;
            font-weight: bold;
            margin: 20px 0;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }}

        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        .summary-card .label {{
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 8px;
        }}

        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}

        .sections {{
            padding: 40px;
        }}

        .section {{
            margin-bottom: 30px;
            border-left: 4px solid #e9ecef;
            padding-left: 20px;
        }}

        .section.preserved {{
            border-left-color: #28a745;
        }}

        .section.altered {{
            border-left-color: #ffc107;
        }}

        .section.missing {{
            border-left-color: #dc3545;
        }}

        .section.added {{
            border-left-color: #17a2b8;
        }}

        .section-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }}

        .section-title {{
            font-size: 1.4em;
            font-weight: 600;
        }}

        .section-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-preserved {{
            background: #d4edda;
            color: #155724;
        }}

        .badge-altered {{
            background: #fff3cd;
            color: #856404;
        }}

        .badge-missing {{
            background: #f8d7da;
            color: #721c24;
        }}

        .badge-added {{
            background: #d1ecf1;
            color: #0c5460;
        }}

        .section-score {{
            margin-left: auto;
            font-size: 1.2em;
            font-weight: bold;
            color: {color};
        }}

        .section-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}

        .detail {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 6px;
        }}

        .detail-label {{
            font-size: 0.85em;
            color: #6c757d;
            margin-bottom: 4px;
        }}

        .detail-value {{
            font-weight: 600;
        }}

        .differences {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            border-radius: 6px;
        }}

        .differences ul {{
            list-style: none;
            padding-left: 0;
        }}

        .differences li {{
            padding: 4px 0;
        }}

        .differences li::before {{
            content: "⚠️ ";
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Content Diff Report</h1>
            <div class="score">{score:.1f}% Preserved</div>
            <div>
                <strong>Source:</strong> {html.escape(Path(report.source_file).name)}<br>
                <strong>Output:</strong> {html.escape(Path(report.output_file).name)}
            </div>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="label">Total Sections</div>
                <div class="value">{report.summary['total_sections']}</div>
            </div>
            <div class="summary-card">
                <div class="label">Preserved</div>
                <div class="value" style="color: #28a745;">{report.summary['preserved_sections']}</div>
            </div>
            <div class="summary-card">
                <div class="label">Altered</div>
                <div class="value" style="color: #ffc107;">{report.summary['altered_sections']}</div>
            </div>
            <div class="summary-card">
                <div class="label">Missing</div>
                <div class="value" style="color: #dc3545;">{report.summary['missing_sections']}</div>
            </div>
        </div>

        <div class="sections">
            <h2 style="margin-bottom: 30px;">Section-by-Section Analysis</h2>
            {sections_html}
        </div>
    </div>
</body>
</html>
"""
        return html

    def _generate_section_html(self, diff: SectionDiff) -> str:
        """Generate HTML for a single section diff."""
        badge_class = f"badge-{diff.status}"

        # Generate details HTML
        details_html = ""
        if diff.source_section and diff.output_section:
            details_html = f"""
            <div class="section-details">
                <div class="detail">
                    <div class="detail-label">Figures</div>
                    <div class="detail-value">{len(diff.source_section.figures)} → {len(diff.output_section.figures)}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Tables</div>
                    <div class="detail-value">{diff.source_section.tables} → {diff.output_section.tables}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Equations</div>
                    <div class="detail-value">{diff.source_section.equations} → {diff.output_section.equations}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Citations</div>
                    <div class="detail-value">{diff.source_section.citations} → {diff.output_section.citations}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Words</div>
                    <div class="detail-value">{diff.source_section.word_count} → {diff.output_section.word_count}</div>
                </div>
            </div>
            """

        # Generate differences HTML
        differences_html = ""
        if len(diff.differences) > 1 or diff.differences[0] != "Content fully preserved":
            differences_list = "\n".join(f"<li>{d}</li>" for d in diff.differences)
            differences_html = f"""
            <div class="differences">
                <strong>Differences:</strong>
                <ul>
                    {differences_list}
                </ul>
            </div>
            """

        return f"""
        <div class="section {diff.status}">
            <div class="section-header">
                <div class="section-title">{diff.title}</div>
                <span class="section-badge {badge_class}">{diff.status}</span>
                <div class="section-score">{diff.preservation_score:.1f}%</div>
            </div>
            {details_html}
            {differences_html}
        </div>
        """
