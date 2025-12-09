"""
File discovery service for LaTeX projects.

This service scans uploaded ZIP files and extracts all LaTeX-related files,
building a complete dependency map and project structure.
"""

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LatexDependencies:
    """Represents LaTeX file dependencies."""

    document_class: str | None = None
    packages: list[str] = field(default_factory=list)
    input_files: list[str] = field(default_factory=list)
    include_files: list[str] = field(default_factory=list)
    bibliography_files: list[str] = field(default_factory=list)
    graphics_paths: list[str] = field(default_factory=list)
    custom_classes: list[str] = field(default_factory=list)
    custom_styles: list[str] = field(default_factory=list)


@dataclass
class ProjectStructure:
    """Represents the structure of a LaTeX project."""

    main_tex_file: Path
    all_tex_files: list[Path] = field(default_factory=list)
    supporting_files: dict[str, list[Path]] = field(default_factory=dict)
    dependencies: LatexDependencies = field(default_factory=LatexDependencies)
    project_dir: Path = Path(".")
    extracted_files: list[Path] = field(default_factory=list)


class FileDiscoveryService:
    """Service for discovering and extracting LaTeX project files."""

    def __init__(self):
        """Initialize the file discovery service."""
        self.logger = __import__("logging").getLogger(__name__)

        # File extensions to look for
        self.latex_extensions = {
            ".tex",
            ".cls",
            ".sty",
            ".bib",
            ".bst",
            ".bbl",
            ".aux",
            ".toc",
            ".lof",
            ".lot",
        }
        self.graphics_extensions = {
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".eps",
            ".ps",
            ".svg",
        }
        self.all_extensions = self.latex_extensions | self.graphics_extensions

        # Patterns for parsing LaTeX files
        self.document_class_pattern = re.compile(
            r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}"
        )
        self.package_pattern = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
        self.input_pattern = re.compile(r"\\input\{([^}]+)\}")
        self.include_pattern = re.compile(r"\\include\{([^}]+)\}")
        self.bibliography_pattern = re.compile(r"\\bibliography\{([^}]+)\}")
        self.graphicspath_pattern = re.compile(r"\\graphicspath\{([^}]+)\}")
        self.graphics_pattern = re.compile(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}"
        )

    def discover_latex_files(self, zip_path: Path) -> ProjectStructure:
        """
        Scan ZIP file and build complete file dependency map.

        Args:
            zip_path: Path to the uploaded ZIP file

        Returns:
            ProjectStructure with all discovered files and dependencies
        """
        self.logger.info(f"Discovering LaTeX files in {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Get all files in the ZIP
                all_files = [
                    Path(f) for f in zip_file.namelist() if not f.endswith("/")
                ]

                # Find main .tex file
                main_tex = self._find_main_tex_file(all_files)
                if not main_tex:
                    raise ValueError("No main .tex file found in ZIP")

                # Extract all LaTeX-related files
                supporting_files = self._categorize_files(all_files)

                # Parse dependencies from main .tex file
                dependencies = self._parse_tex_dependencies(zip_file, main_tex)

                # Build project structure
                project_structure = ProjectStructure(
                    main_tex_file=main_tex,
                    all_tex_files=[f for f in all_files if f.suffix == ".tex"],
                    supporting_files=supporting_files,
                    dependencies=dependencies,
                    extracted_files=all_files,
                )

                self.logger.info(
                    f"Discovered {len(all_files)} files, main file: {main_tex}"
                )
                return project_structure

        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP file: {e}") from e
        except Exception as e:
            raise ValueError(f"Error discovering files: {e}") from e

    def extract_project_files(
        self, zip_path: Path, output_dir: Path
    ) -> ProjectStructure:
        """
        Extract and organize all project files maintaining directory structure.

        Args:
            zip_path: Path to the uploaded ZIP file
            output_dir: Directory to extract files to

        Returns:
            ProjectStructure with extracted files
        """
        self.logger.info(f"Extracting project files from {zip_path} to {output_dir}")

        # First discover the structure
        project_structure = self.discover_latex_files(zip_path)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Extract all files maintaining directory structure
                for file_path in project_structure.extracted_files:
                    # Skip directories
                    if file_path.suffix == "":
                        continue

                    # Extract to output directory
                    extract_path = output_dir / file_path
                    extract_path.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file content
                    with (
                        zip_file.open(str(file_path)) as source_file,
                        open(extract_path, "wb") as target_file,
                    ):
                        target_file.write(source_file.read())

                # Update project structure with actual extracted paths
                project_structure.main_tex_file = (
                    output_dir / project_structure.main_tex_file
                )
                project_structure.project_dir = output_dir

                self.logger.info(
                    f"Extracted {len(project_structure.extracted_files)} "
                    f"files to {output_dir}"
                )
                return project_structure

        except Exception as e:
            raise ValueError(f"Error extracting files: {e}") from e

    def _find_main_tex_file(self, files: list[Path]) -> Path | None:
        """
        Identify main .tex file from candidates.

        Args:
            files: List of all files in the ZIP

        Returns:
            Path to main .tex file or None if not found
        """
        tex_files = [f for f in files if f.suffix == ".tex"]

        if not tex_files:
            return None

        # If only one .tex file, that's it
        if len(tex_files) == 1:
            return tex_files[0]

        # Look for common main file names
        main_candidates = [
            "main.tex",
            "document.tex",
            "paper.tex",
            "article.tex",
            "manuscript.tex",
        ]
        for candidate in main_candidates:
            for tex_file in tex_files:
                if tex_file.name.lower() == candidate.lower():
                    return tex_file

        # Look for files with \documentclass
        for _tex_file in tex_files:
            try:
                # This is a simplified check - in real implementation we'd read the file
                # For now, assume the largest .tex file is the main one
                pass
            except Exception:
                continue

        # Default to the largest .tex file
        return max(tex_files, key=lambda f: f.name)

    def _categorize_files(self, files: list[Path]) -> dict[str, list[Path]]:
        """
        Categorize files by type.

        Args:
            files: List of all files

        Returns:
            Dictionary categorizing files by type
        """
        categories = {
            "tex_files": [],
            "class_files": [],
            "style_files": [],
            "bib_files": [],
            "graphics_files": [],
            "other_files": [],
        }

        for file_path in files:
            suffix = file_path.suffix.lower()

            if suffix == ".tex":
                categories["tex_files"].append(file_path)
            elif suffix == ".cls":
                categories["class_files"].append(file_path)
            elif suffix == ".sty":
                categories["style_files"].append(file_path)
            elif suffix in [".bib", ".bst", ".bbl"]:
                categories["bib_files"].append(file_path)
            elif suffix in self.graphics_extensions:
                categories["graphics_files"].append(file_path)
            else:
                categories["other_files"].append(file_path)

        return categories

    def _parse_tex_dependencies(
        self, zip_file: zipfile.ZipFile, main_tex: Path
    ) -> LatexDependencies:
        """
        Parse .tex file to extract all dependencies.

        Args:
            zip_file: Open ZIP file object
            main_tex: Path to main .tex file

        Returns:
            LatexDependencies object with all found dependencies
        """
        dependencies = LatexDependencies()

        try:
            # Read the main .tex file content
            with zip_file.open(str(main_tex)) as f:
                content = f.read().decode("utf-8", errors="ignore")

            # Extract document class
            doc_class_match = self.document_class_pattern.search(content)
            if doc_class_match:
                dependencies.document_class = doc_class_match.group(1)
                dependencies.custom_classes.append(doc_class_match.group(1))

            # Extract packages
            package_matches = self.package_pattern.findall(content)
            dependencies.packages = list(set(package_matches))

            # Extract input files
            input_matches = self.input_pattern.findall(content)
            dependencies.input_files = list(set(input_matches))

            # Extract include files
            include_matches = self.include_pattern.findall(content)
            dependencies.include_files = list(set(include_matches))

            # Extract bibliography files
            bib_matches = self.bibliography_pattern.findall(content)
            dependencies.bibliography_files = list(set(bib_matches))

            # Extract graphics paths
            graphics_path_matches = self.graphicspath_pattern.findall(content)
            dependencies.graphics_paths = list(set(graphics_path_matches))

            # Extract graphics files
            graphics_matches = self.graphics_pattern.findall(content)
            dependencies.graphics_paths.extend(list(set(graphics_matches)))

            self.logger.info(
                f"Parsed dependencies: {len(dependencies.packages)} packages, "
                f"{len(dependencies.input_files)} input files, "
                f"{len(dependencies.include_files)} include files"
            )

        except Exception as e:
            self.logger.warning(f"Error parsing dependencies from {main_tex}: {e}")

        return dependencies

    def find_missing_files(self, project_structure: ProjectStructure) -> list[str]:
        """
        Find files that are referenced but missing from the project.

        Args:
            project_structure: The project structure to analyze

        Returns:
            List of missing file names
        """
        missing_files = []
        dependencies = project_structure.dependencies

        # Check for missing input files
        for input_file in dependencies.input_files:
            if not any(
                f.name == input_file or f.name == f"{input_file}.tex"
                for f in project_structure.all_tex_files
            ):
                missing_files.append(input_file)

        # Check for missing include files
        for include_file in dependencies.include_files:
            if not any(
                f.name == include_file or f.name == f"{include_file}.tex"
                for f in project_structure.all_tex_files
            ):
                missing_files.append(include_file)

        # Check for missing bibliography files
        for bib_file in dependencies.bibliography_files:
            if not any(
                f.name == bib_file or f.name == f"{bib_file}.bib"
                for f in project_structure.supporting_files.get("bib_files", [])
            ):
                missing_files.append(bib_file)

        # Check for missing custom classes
        for custom_class in dependencies.custom_classes:
            if not any(
                f.name == custom_class or f.name == f"{custom_class}.cls"
                for f in project_structure.supporting_files.get("class_files", [])
            ):
                missing_files.append(custom_class)

        return missing_files

    def validate_project_structure(
        self, project_structure: ProjectStructure
    ) -> dict[str, Any]:
        """
        Validate the project structure and return diagnostics.

        Args:
            project_structure: The project structure to validate

        Returns:
            Dictionary with validation results and suggestions
        """
        diagnostics = {"valid": True, "warnings": [], "errors": [], "suggestions": []}

        # Check if main file exists
        if not project_structure.main_tex_file.exists():
            diagnostics["valid"] = False
            diagnostics["errors"].append(
                f"Main file not found: {project_structure.main_tex_file}"
            )

        # Check for missing files
        missing_files = self.find_missing_files(project_structure)
        if missing_files:
            diagnostics["warnings"].append(f"Missing referenced files: {missing_files}")
            diagnostics["suggestions"].append(
                "Ensure all referenced files are included in the ZIP"
            )

        # Check for custom document classes
        if project_structure.dependencies.custom_classes:
            diagnostics["suggestions"].append(
                f"Custom document classes found: "
                f"{project_structure.dependencies.custom_classes}. "
                "Ensure these are available in the LaTeX installation."
            )

        # Check for many packages
        if len(project_structure.dependencies.packages) > 20:
            diagnostics["warnings"].append(
                f"Many packages required "
                f"({len(project_structure.dependencies.packages)}). "
                "Some may not be available in the Docker environment."
            )

        return diagnostics
