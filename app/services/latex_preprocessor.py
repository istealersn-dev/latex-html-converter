"""
LaTeX preprocessor service for handling custom document classes and commands.

This service detects custom document classes and ensures their supporting files
are available to LaTeXML, rather than replacing them with standard classes.
"""

import re
from pathlib import Path
from typing import Any

from loguru import logger


class LaTeXPreprocessor:
    """Service for preprocessing LaTeX files before conversion."""

    def __init__(self):
        """Initialize the LaTeX preprocessor."""
        self.logger = logger

    def __init__(self):
        """Initialize the LaTeX preprocessor."""
        self.logger = logger

    def detect_custom_class(
        self, input_file: Path, project_dir: Path | None = None
    ) -> dict[str, Any] | None:
        """
        Detect custom document class and find its supporting files.

        Args:
            input_file: Path to input LaTeX file
            project_dir: Project directory to search for class files

        Returns:
            Dict with class info (name, cls_file_path, sty_files) or None
        """
        try:
            content = input_file.read_text(encoding="utf-8", errors="ignore")

            # Pattern to match \documentclass[options]{class}
            class_pattern = re.compile(
                r"\\documentclass(?:\[([^\]]*)\])?\{([^}]+)\}", re.IGNORECASE
            )

            match = class_pattern.search(content)
            if not match:
                return None

            options = match.group(1) or ""
            class_name = match.group(2).strip()

            # Check if it's a standard class (article, book, report, etc.)
            standard_classes = {
                "article",
                "book",
                "report",
                "letter",
                "slides",
                "memoir",
                "scrartcl",
                "scrbook",
                "scrreprt",
            }
            if class_name.lower() in standard_classes:
                return None

            # It's a custom class - find the .cls file
            self.logger.info(f"Detected custom document class: {class_name}")

            # Search for class file
            cls_file = None
            search_dirs = []

            if project_dir and project_dir.exists():
                search_dirs.append(project_dir)

            # Also search in input file's directory and parent
            search_dirs.append(input_file.parent)
            if input_file.parent.parent.exists():
                search_dirs.append(input_file.parent.parent)

            for search_dir in search_dirs:
                # Look for class file
                potential_cls = search_dir / f"{class_name}.cls"
                if potential_cls.exists():
                    cls_file = potential_cls
                    self.logger.info(f"Found class file: {cls_file}")
                    break

                # Also check subdirectories
                for subdir in search_dir.rglob("*"):
                    if subdir.is_dir():
                        potential_cls = subdir / f"{class_name}.cls"
                        if potential_cls.exists():
                            cls_file = potential_cls
                            self.logger.info(f"Found class file: {cls_file}")
                            break
                    if cls_file:
                        break

            # Find related style files (same name.sty)
            sty_files = []
            for search_dir in search_dirs:
                potential_sty = search_dir / f"{class_name}.sty"
                if potential_sty.exists() and potential_sty not in sty_files:
                    sty_files.append(potential_sty)

            return {
                "class_name": class_name,
                "options": options,
                "cls_file": cls_file,
                "sty_files": sty_files,
                "search_dirs": [str(d) for d in search_dirs if d.exists()],
            }

        except Exception as exc:
            self.logger.warning(f"Failed to detect custom class: {exc}")
            return None
