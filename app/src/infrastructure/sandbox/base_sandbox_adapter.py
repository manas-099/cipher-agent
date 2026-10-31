# app/src/infrastructure/sandbox/base_sandbox_adapter.py
# Shared SandboxPort implementation on top of a persistent SandboxSession.
# Language adapters only provide command strings and test-output parsing.

from __future__ import annotations

import re
import shlex
from abc import abstractmethod

from app.src.config.settings import SandboxSettings, get_settings
from app.src.infrastructure.sandbox.sandbox_session import SandboxSession
from app.src.logger.logger import get_logger
from app.src.ports.outbound.sandbox_port import (
    ExecutionResult,
    LintIssue,
    LintResult,
    SandboxLanguage,
    SandboxPort,
    TestResult,
)

_ISSUE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):?\s*(?P<message>.+)$"
)
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/+-]*$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


class BaseSandboxAdapter(SandboxPort):
    """
    Every sandbox adapter executes against the same session container.
    Subclasses decide the image-independent command for each operation.
    """

    language: SandboxLanguage

    def __init__(
        self,
        session: SandboxSession,
        settings: SandboxSettings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings().sandbox
        self._logger = get_logger(self.__class__.__module__)

    # ── subclass contract ─────────────────────────────────────────────────────

    @abstractmethod
    def _code_command(self, file_name: str, args: list[str] | None) -> str:
        ...

    @abstractmethod
    def _test_command(self, target: str | None, framework: str) -> str:
        ...

    @abstractmethod
    def _lint_command(self, target: str | None, linter: str, fix: bool) -> str:
        ...

    @abstractmethod
    def _install_command(
        self, package: str, manager: str, version: str | None
    ) -> str:
        ...

    # ── SandboxPort: execution ────────────────────────────────────────────────

    def run_code(
        self,
        file_path: str,
        language: SandboxLanguage,
        timeout: int = 30,
        args: list[str] | None = None,
    ) -> ExecutionResult:
        relative = self._session.relative_path(file_path)
        command = self._code_command(relative, args)
        return self._session.exec(command, timeout=timeout)

    def run_command(
        self,
        command: str,
        language: SandboxLanguage,
        working_dir: str | None = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        workdir = (
            self._session.relative_path(working_dir) if working_dir else None
        )
        return self._session.exec(command, timeout=timeout, workdir=workdir)

    # ── SandboxPort: tests ────────────────────────────────────────────────────

    def run_tests(
        self,
        path: str,
        framework: str = "auto",
        test_file: str | None = None,
        timeout: int = 60,
    ) -> TestResult:
        relative = self._session.relative_path(path)
        if test_file:
            target = (
                f"{relative}/{test_file}" if relative != "." else test_file
            )
        else:
            target = relative if relative != "." else None
        command = self._test_command(target, framework)
        result = self._session.exec(command, timeout=timeout)
        return self._parse_tests(result)

    def _parse_tests(self, result: ExecutionResult) -> TestResult:
        text = f"{result.stdout}\n{result.stderr}"
        return TestResult(
            passed=self._count(r"(\d+)\s+passed", text),
            failed=self._count(r"(\d+)\s+failed", text),
            errors=self._count(r"(\d+)\s+error(?:s)?\b", text),
            output=result.output,
            exit_code=result.exit_code,
        )

    # ── SandboxPort: lint ─────────────────────────────────────────────────────

    def lint_code(
        self,
        path: str,
        linter: str = "auto",
        fix: bool = False,
    ) -> LintResult:
        relative = self._session.relative_path(path)
        target = relative if relative != "." else None
        command = self._lint_command(target, linter, fix)
        result = self._session.exec(
            command,
            timeout=self._settings.TIMEOUT_SECONDS,
        )
        return self._parse_lint(result)

    def _parse_lint(self, result: ExecutionResult) -> LintResult:
        issues: list[LintIssue] = []
        for line in f"{result.stdout}\n{result.stderr}".splitlines():
            match = _ISSUE_RE.match(line.strip())
            if not match:
                continue
            message = match.group("message").strip()
            issues.append(
                LintIssue(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("col")),
                    message=message,
                    severity=self._severity(message),
                )
            )

        errors = sum(1 for issue in issues if issue.severity == "error")
        warnings = len(issues) - errors
        if result.exit_code != 0 and not issues:
            errors = 1

        return LintResult(
            error_count=errors,
            warning_count=warnings,
            output=result.output,
            issues=issues,
        )

    # ── SandboxPort: package install ──────────────────────────────────────────

    def install_package(
        self,
        package: str,
        manager: str = "auto",
        version: str | None = None,
    ) -> ExecutionResult:
        if not _PACKAGE_RE.match(package):
            return self._invalid(f"Invalid package name: {package}")
        if version and not _VERSION_RE.match(version):
            return self._invalid(f"Invalid version: {version}")

        command = self._install_command(package, manager, version)
        with self._session.network():
            return self._session.exec(
                command,
                timeout=self._settings.TIMEOUT_SECONDS * 3,
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _severity(message: str) -> str:
        lowered = message.lower()
        if "[warning" in lowered or lowered.startswith("warning"):
            return "warning"
        if "[error" in lowered or lowered.startswith("error"):
            return "error"
        if re.match(r"W\d+\b", message):
            return "warning"
        return "error"

    @staticmethod
    def _quote_args(args: list[str] | None) -> str:
        return "".join(f" {shlex.quote(arg)}" for arg in (args or []))

    @staticmethod
    def _count(pattern: str, text: str) -> int:
        match = re.search(pattern, text)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _invalid(message: str) -> ExecutionResult:
        return ExecutionResult(
            stdout="",
            stderr=message,
            exit_code=-1,
            timed_out=False,
        )
