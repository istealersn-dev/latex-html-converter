"""
Shell utilities for safe subprocess execution.

This module provides secure subprocess management with proper error handling,
timeout management, and security considerations.
"""

import subprocess
from pathlib import Path
from typing import NamedTuple

from loguru import logger


class CommandResult(NamedTuple):
    """Result of a command execution."""
    returncode: int
    stdout: str
    stderr: str


def run_command_safely(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 300,
    env: dict[str, str] | None = None
) -> CommandResult:
    """
    Run a command safely with proper error handling and security.

    Args:
        cmd: Command to run as list of strings
        cwd: Working directory for the command
        timeout: Timeout in seconds (default: 5 minutes)
        env: Environment variables

    Returns:
        CommandResult with return code and output

    Raises:
        subprocess.TimeoutExpired: If command times out
        subprocess.CalledProcessError: If command fails
        ValueError: If command contains unsafe characters
    """
    # Security: Validate command for safety
    _validate_command_safety(cmd)

    # Prepare environment
    if env is None:
        env = {}

    # Add security environment variables
    env.update({
        "SHELL": "/bin/bash",  # Use bash for consistency
        "PATH": "/usr/bin:/bin:/usr/local/bin",  # Restricted PATH
    })

    logger.debug(f"Running command: {' '.join(cmd)}")
    if cwd:
        logger.debug(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False  # Don't raise exception on non-zero return code
        )

        logger.debug(f"Command completed with return code: {result.returncode}")
        if result.stdout:
            logger.debug(f"STDOUT: {result.stdout[:200]}...")
        if result.stderr:
            logger.debug(f"STDERR: {result.stderr[:200]}...")

        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        raise
    except Exception as exc:
        logger.error(f"Command failed: {exc}")
        raise


def _validate_command_safety(cmd: list[str]) -> None:
    """
    Validate command for security issues.

    Args:
        cmd: Command to validate

    Raises:
        ValueError: If command contains unsafe patterns
    """
    # Dangerous patterns to avoid (but allow LaTeX flags)
    dangerous_patterns = [
        '&&', '||', ';', '|', '>', '<', '>>', '<<', '&',
        '$(', '`', '$(', '${', 'exec', 'eval', 'source',
        'rm -rf', 'rmdir', 'del', 'format', 'fdisk',
        'mkfs', 'dd', 'shutdown', 'reboot'
    ]
    
    # Additional check for dangerous commands (but not flags)
    dangerous_commands = ['halt', 'kill', 'pkill']
    for cmd_part in cmd:
        if cmd_part in dangerous_commands and not cmd_part.startswith('--'):
            raise ValueError(f"Unsafe command detected: {cmd_part}")

    cmd_str = ' '.join(cmd).lower()

    for pattern in dangerous_patterns:
        if pattern in cmd_str:
            raise ValueError(f"Unsafe command pattern detected: {pattern}")

    # Check for shell injection attempts
    dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '~', '!']
    if any(char in cmd_str for char in dangerous_chars):
        # Allow some safe characters but log warning
        logger.warning(f"Command contains potentially unsafe characters: {cmd_str}")
    
    # Additional security checks
    if any(word in cmd_str for word in ['sudo', 'su', 'chmod', 'chown', 'passwd']):
        raise ValueError(f"Potentially dangerous command detected: {cmd_str}")
    
    # Check for path traversal attempts
    if '..' in cmd_str or '/etc/' in cmd_str or '/sys/' in cmd_str:
        raise ValueError(f"Path traversal or system directory access detected: {cmd_str}")


def run_command_with_retry(
    cmd: list[str],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs
) -> CommandResult:
    """
    Run command with retry logic for transient failures.

    Args:
        cmd: Command to run
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        **kwargs: Additional arguments for run_command_safely

    Returns:
        CommandResult from successful execution

    Raises:
        subprocess.TimeoutExpired: If all retries timeout
        subprocess.CalledProcessError: If all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return run_command_safely(cmd, **kwargs)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            last_exception = exc
            if attempt < max_retries:
                logger.warning(f"Command failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {retry_delay}s...")
                import time
                time.sleep(retry_delay)
            else:
                logger.error(f"Command failed after {max_retries + 1} attempts")
                break

    raise last_exception


def check_command_available(cmd: str) -> bool:
    """
    Check if a command is available in the system.

    Args:
        cmd: Command to check

    Returns:
        True if command is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
            text=True,
            timeout=10, check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_command_version(cmd: str, version_flag: str = "--version") -> str | None:
    """
    Get version information for a command.

    Args:
        cmd: Command to check
        version_flag: Flag to get version (default: --version)

    Returns:
        Version string or None if not available
    """
    try:
        result = run_command_safely([cmd, version_flag], timeout=30)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
