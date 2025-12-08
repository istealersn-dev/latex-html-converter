"""
Package manager service for LaTeX packages.

This service detects required LaTeX packages from .tex files and manages
their installation using tlmgr (TeX Live Manager).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.utils.shell import run_command_safely


@dataclass
class PackageInfo:
    """Information about a LaTeX package."""

    name: str
    installed: bool = False
    version: str | None = None
    dependencies: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass
class InstallResult:
    """Result of package installation."""

    success: bool
    installed_packages: list[str] = field(default_factory=list)
    failed_packages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PackageManagerService:
    """Service for managing LaTeX packages."""

    def __init__(self, timeout: int = 300):
        """
        Initialize the package manager service.

        Args:
            timeout: Timeout for package installation commands in seconds
        """
        self.logger = __import__("logging").getLogger(__name__)
        self.timeout = timeout

        # Common package mappings for different LaTeX distributions
        self.package_mappings = {
            "amsmath": "texlive-latex-recommended",
            "amsfonts": "texlive-latex-recommended",
            "amssymb": "texlive-latex-recommended",
            "graphicx": "texlive-latex-recommended",
            "hyperref": "texlive-latex-recommended",
            "url": "texlive-latex-recommended",
            "booktabs": "texlive-latex-extra",
            "microtype": "texlive-latex-extra",
            "xcolor": "texlive-latex-extra",
            "multicol": "texlive-latex-extra",
            "enumitem": "texlive-latex-extra",
            "mathtools": "texlive-latex-extra",
            "algorithm": "texlive-latex-extra",
            "algorithmic": "texlive-latex-extra",
            "caption": "texlive-latex-extra",
            "cleveref": "texlive-latex-extra",
            "titlesec": "texlive-latex-extra",
            "multirow": "texlive-latex-extra",
            "adjustbox": "texlive-latex-extra",
            "stmaryrd": "texlive-latex-extra",
            "bbm": "texlive-latex-extra",
            "comment": "texlive-latex-extra",
            "bm": "texlive-latex-extra",
            "xifthen": "texlive-latex-extra",
            "nccmath": "texlive-latex-extra",
            "soul": "texlive-latex-extra",
            "wrapfig": "texlive-latex-extra",
            "nicefrac": "texlive-latex-extra",
            "framed": "texlive-latex-extra",
            "xargs": "texlive-latex-extra",
            "inputenc": "texlive-latex-recommended",
            "fontenc": "texlive-latex-recommended",
            "amsthm": "texlive-latex-recommended",
            "subfigure": "texlive-latex-extra",
            "export": "texlive-latex-extra",
        }

        # Patterns for parsing LaTeX files
        self.package_pattern = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
        self.document_class_pattern = re.compile(
            r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}"
        )

    def detect_required_packages(self, tex_file: Path) -> list[str]:
        """
        Parse .tex file and extract all usepackage declarations.

        Args:
            tex_file: Path to the .tex file to analyze

        Returns:
            List of required package names
        """
        self.logger.info(f"Detecting required packages in {tex_file}")

        try:
            with open(tex_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Find all \usepackage declarations
            package_matches = self.package_pattern.findall(content)
            packages = list(set(package_matches))

            # Also check for document class dependencies
            doc_class_matches = self.document_class_pattern.findall(content)
            for doc_class in doc_class_matches:
                # Some document classes require specific packages
                if doc_class in ["article", "report", "book"]:
                    packages.extend(["amsmath", "graphicx"])
                elif doc_class in ["beamer"]:
                    packages.extend(["amsmath", "graphicx", "hyperref"])

            # Remove duplicates and sort
            packages = sorted(list(set(packages)))

            self.logger.info(f"Detected {len(packages)} required packages: {packages}")
            return packages

        except Exception as e:
            self.logger.error(f"Error detecting packages from {tex_file}: {e}")
            return []

    def check_package_availability(self, packages: list[str]) -> dict[str, bool]:
        """
        Check which packages are available in current TeX installation.

        Args:
            packages: List of package names to check

        Returns:
            Dictionary mapping package names to availability status
        """
        # Check if tlmgr is available first
        if not self._is_tlmgr_available():
            self.logger.debug(
                "tlmgr not available, skipping package availability check"
            )
            # Return False for all packages if tlmgr is not available
            return {package: False for package in packages}

        self.logger.info(f"Checking availability of {len(packages)} packages")

        availability = {}

        for package in packages:
            try:
                # Try to check if package is available using tlmgr
                result = run_command_safely(
                    ["tlmgr", "info", "--only-installed", package], timeout=30
                )
                availability[package] = result.returncode == 0

            except FileNotFoundError:
                # tlmgr not found - silently mark as unavailable
                availability[package] = False
            except Exception as e:
                self.logger.debug(f"Error checking package {package}: {e}")
                availability[package] = False

        available_count = sum(1 for available in availability.values() if available)
        self.logger.info(f"Found {available_count}/{len(packages)} packages available")

        return availability

    def install_missing_packages(self, packages: list[str]) -> InstallResult:
        """
        Install missing packages using tlmgr or apt.

        Args:
            packages: List of package names to install

        Returns:
            InstallResult with installation status
        """
        # Check tool availability first
        tlmgr_available = self._is_tlmgr_available()
        apt_available = self._is_apt_available()

        if not tlmgr_available and not apt_available:
            self.logger.debug(
                "Package installation tools (tlmgr/apt) not available - "
                "skipping package installation"
            )
            # Return result indicating packages couldn't be installed
            # (but this is expected)
            result = InstallResult(success=False)
            result.failed_packages = packages
            result.warnings.append(
                "Package installation tools not available on this system"
            )
            return result

        self.logger.info(f"Attempting to install {len(packages)} packages")

        result = InstallResult(success=True)

        for package in packages:
            try:
                # Try tlmgr first (preferred for TeX Live)
                install_success = self._install_with_tlmgr(package)

                if install_success:
                    result.installed_packages.append(package)
                    self.logger.info(f"Successfully installed {package} with tlmgr")
                else:
                    # Try apt as fallback
                    install_success = self._install_with_apt(package)

                    if install_success:
                        result.installed_packages.append(package)
                        self.logger.info(f"Successfully installed {package} with apt")
                    else:
                        result.failed_packages.append(package)
                        result.errors.append(f"Failed to install {package}")
                        # Only log as error if tools are available
                        # but installation failed
                        if tlmgr_available or apt_available:
                            self.logger.debug(
                                f"Could not install {package} "
                                f"(tools available but installation failed)"
                            )
                        else:
                            self.logger.debug(
                                f"Could not install {package} (tools not available)"
                            )

            except Exception as e:
                result.failed_packages.append(package)
                result.errors.append(f"Error installing {package}: {e}")
                # Only log as error if it's unexpected
                if tlmgr_available or apt_available:
                    self.logger.debug(f"Error installing {package}: {e}")

        result.success = len(result.failed_packages) == 0

        if result.failed_packages:
            if tlmgr_available or apt_available:
                self.logger.debug(
                    f"Could not install {len(result.failed_packages)} "
                    f"packages: {result.failed_packages}"
                )
            else:
                self.logger.debug(
                    f"Package installation skipped - tools not available "
                    f"({len(result.failed_packages)} packages)"
                )

        return result

    def _is_tlmgr_available(self) -> bool:
        """
        Check if tlmgr is available on the system.

        Returns:
            True if tlmgr is available, False otherwise
        """
        try:
            result = run_command_safely(["tlmgr", "--version"], timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, Exception):
            return False

    def _install_with_tlmgr(self, package: str) -> bool:
        """
        Install package using tlmgr.

        Args:
            package: Package name to install

        Returns:
            True if installation successful, False otherwise
        """
        if not self._is_tlmgr_available():
            return False

        try:
            # First try to install the package directly
            result = run_command_safely(
                ["tlmgr", "install", package], timeout=self.timeout
            )

            if result.returncode == 0:
                return True

            # If direct installation fails, try to find the package in collections
            collection_result = run_command_safely(
                ["tlmgr", "search", "--global", "--file", f"{package}.sty"], timeout=30
            )

            if collection_result.returncode == 0:
                # Try to install the collection
                collection_name = self._extract_collection_name(
                    collection_result.stdout
                )
                if collection_name:
                    collection_install = run_command_safely(
                        ["tlmgr", "install", collection_name], timeout=self.timeout
                    )
                    return collection_install.returncode == 0

            return False

        except FileNotFoundError:
            # tlmgr not found - return False silently
            return False
        except Exception as e:
            self.logger.debug(f"tlmgr installation failed for {package}: {e}")
            return False

    def _is_apt_available(self) -> bool:
        """
        Check if apt-get is available on the system.

        Returns:
            True if apt-get is available, False otherwise
        """
        try:
            result = run_command_safely(["apt-get", "--version"], timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, Exception):
            return False

    def _install_with_apt(self, package: str) -> bool:
        """
        Install package using apt (fallback method).

        Args:
            package: Package name to install

        Returns:
            True if installation successful, False otherwise
        """
        if not self._is_apt_available():
            return False

        try:
            # Map LaTeX package to apt package
            apt_package = self.package_mappings.get(package, "texlive-latex-extra")

            result = run_command_safely(["apt-get", "update"], timeout=60)

            if result.returncode != 0:
                return False

            install_result = run_command_safely(
                ["apt-get", "install", "-y", apt_package], timeout=self.timeout
            )

            return install_result.returncode == 0

        except FileNotFoundError:
            # apt-get not found - return False silently
            return False
        except Exception as e:
            self.logger.debug(f"apt installation failed for {package}: {e}")
            return False

    def _extract_collection_name(self, tlmgr_output: str) -> str | None:
        """
        Extract collection name from tlmgr search output.

        Args:
            tlmgr_output: Output from tlmgr search command

        Returns:
            Collection name if found, None otherwise
        """
        lines = tlmgr_output.strip().split("\n")
        for line in lines:
            if "collection-" in line:
                # Extract collection name
                parts = line.split()
                for part in parts:
                    if part.startswith("collection-"):
                        return part
        return None

    def get_package_dependencies(self, package: str) -> list[str]:
        """
        Get dependencies for a LaTeX package.

        Args:
            package: Package name

        Returns:
            List of dependency package names
        """
        try:
            result = run_command_safely(
                ["tlmgr", "info", "--only-installed", package], timeout=30
            )

            if result.returncode == 0:
                # Parse dependencies from tlmgr output
                dependencies = []
                lines = result.stdout.split("\n")
                in_deps = False

                for line in lines:
                    if "dependencies:" in line.lower():
                        in_deps = True
                        continue
                    elif in_deps and line.strip():
                        if line.startswith(" "):
                            # This is a dependency line
                            dep_name = line.strip().split()[0]
                            dependencies.append(dep_name)
                        else:
                            break

                return dependencies

        except Exception as e:
            self.logger.warning(f"Error getting dependencies for {package}: {e}")

        return []

    def get_package_info(self, package: str) -> PackageInfo:
        """
        Get detailed information about a package.

        Args:
            package: Package name

        Returns:
            PackageInfo object with package details
        """
        try:
            result = run_command_safely(["tlmgr", "info", package], timeout=30)

            info = PackageInfo(name=package)

            if result.returncode == 0:
                info.installed = True
                # Parse version and description from output
                lines = result.stdout.split("\n")
                for line in lines:
                    if "version:" in line.lower():
                        info.version = line.split(":", 1)[1].strip()
                    elif "description:" in line.lower():
                        info.description = line.split(":", 1)[1].strip()

            return info

        except Exception as e:
            self.logger.warning(f"Error getting info for {package}: {e}")
            return PackageInfo(name=package)

    def update_package_database(self) -> bool:
        """
        Update the package database.

        Returns:
            True if update successful, False otherwise
        """
        try:
            self.logger.info("Updating package database")

            # Update tlmgr database
            result = run_command_safely(["tlmgr", "update", "--self"], timeout=120)

            if result.returncode == 0:
                # Update package list
                update_result = run_command_safely(
                    ["tlmgr", "update", "--list"], timeout=60
                )
                return update_result.returncode == 0

            return False

        except Exception as e:
            self.logger.error(f"Error updating package database: {e}")
            return False

    def get_installed_packages(self) -> list[str]:
        """
        Get list of all installed packages.

        Returns:
            List of installed package names
        """
        try:
            result = run_command_safely(
                ["tlmgr", "list", "--only-installed"], timeout=60
            )

            if result.returncode == 0:
                packages = []
                lines = result.stdout.split("\n")
                for line in lines:
                    if line.strip() and not line.startswith("tlmgr:"):
                        package_name = line.split()[0]
                        packages.append(package_name)

                return packages

        except Exception as e:
            self.logger.error(f"Error getting installed packages: {e}")

        return []

    def validate_installation(self) -> dict[str, Any]:
        """
        Validate the LaTeX installation and package manager.

        Returns:
            Dictionary with validation results
        """
        validation = {
            "tlmgr_available": False,
            "latex_available": False,
            "packages_installed": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Check if tlmgr is available
            tlmgr_result = run_command_safely(["tlmgr", "--version"], timeout=30)
            validation["tlmgr_available"] = tlmgr_result.returncode == 0

            # Check if latex is available
            latex_result = run_command_safely(["latex", "--version"], timeout=30)
            validation["latex_available"] = latex_result.returncode == 0

            # Count installed packages
            installed_packages = self.get_installed_packages()
            validation["packages_installed"] = len(installed_packages)

            if not validation["tlmgr_available"]:
                validation["errors"].append(
                    "tlmgr not available - package management disabled"
                )

            if not validation["latex_available"]:
                validation["errors"].append(
                    "LaTeX not available - compilation will fail"
                )

            if validation["packages_installed"] < 100:
                validation["warnings"].append(
                    "Few packages installed - may need texlive-full"
                )

        except Exception as e:
            validation["errors"].append(f"Validation error: {e}")

        return validation
