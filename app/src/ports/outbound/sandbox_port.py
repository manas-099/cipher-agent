# app/src/ports/outbound/sandbox_port.py
# Contract for running code in an isolated Docker sandbox.
# PythonSandbox, NodeSandbox, BashSandbox all implement this.
# Domain never touches Docker SDK directly.

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


# ── supported languages ───────────────────────────────────────────────────────

class SandboxLanguage(str, Enum):
    PYTHON = "python"
    NODE   = "node"
    BASH   = "bash"


# ── return types ──────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """
    Result of running code or a command in the sandbox.
    Returned by both run_code() and run_command().
    """
    stdout    : str
    stderr    : str
    exit_code : int
    timed_out : bool
    duration_seconds: float = field(default=0.0)

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def failed(self) -> bool:
        return not self.success

    @property
    def output(self) -> str:
        """Combined stdout + stderr for LLM consumption."""
        parts = []
        if self.stdout.strip():
            parts.append(self.stdout.strip())
        if self.stderr.strip():
            parts.append(f"STDERR:\n{self.stderr.strip()}")
        if self.timed_out:
            parts.append("TIMED OUT")
        return "\n".join(parts) if parts else "(no output)"


@dataclass
class TestResult:
    """
    Result of running a test suite.
    Wraps ExecutionResult with parsed test counts.
    """
    passed    : int
    failed    : int
    errors    : int
    output    : str
    exit_code : int

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors


@dataclass
class LintResult:
    """Result of running a linter."""
    error_count   : int
    warning_count : int
    output        : str
    issues        : list[LintIssue] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.error_count == 0


@dataclass
class LintIssue:
    file     : str
    line     : int
    column   : int
    message  : str
    severity : str    # "error" | "warning"


# ── the port ──────────────────────────────────────────────────────────────────

class SandboxPort(ABC):
    """
    Contract for isolated code execution.
    Every sandbox spins up a fresh Docker container per call.
    """

    @abstractmethod
    def run_code(
        self,
        file_path : str,
        language  : SandboxLanguage,
        timeout   : int = 30,
        args      : list[str] | None = None,
    ) -> ExecutionResult:
        """
        Run a code file inside Docker.
        Container is created fresh and destroyed after each run.

        Args:
            file_path : absolute path to the file to run
            language  : which runtime to use
            timeout   : seconds before container is killed
            args      : command line args passed to the script
        """
        ...

    @abstractmethod
    def run_command(
        self,
        command     : str,
        language    : SandboxLanguage,
        working_dir : str | None = None,
        timeout     : int = 30,
    ) -> ExecutionResult:
        """
        Run a raw shell command inside Docker.
        Used for npm install, pip install, build commands etc.
        """
        ...

    @abstractmethod
    def run_tests(
        self,
        path      : str,
        framework : str = "auto",
        test_file : str | None = None,
        timeout   : int = 60,
    ) -> TestResult:
        """
        Run test suite and return parsed results.
        framework: "pytest" | "jest" | "auto"
        """
        ...

    @abstractmethod
    def lint_code(
        self,
        path   : str,
        linter : str = "auto",
        fix    : bool = False,
    ) -> LintResult:
        """
        Run linter and return structured issues.
        linter: "flake8" | "eslint" | "auto"
        """
        ...

    @abstractmethod
    def install_package(
        self,
        package : str,
        manager : str = "auto",
        version : str | None = None,
    ) -> ExecutionResult:
        """
        Install a package inside the sandbox.
        manager: "pip" | "npm" | "auto"
        """
        ...