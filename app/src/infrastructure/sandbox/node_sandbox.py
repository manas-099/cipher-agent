# app/src/infrastructure/sandbox/node_sandbox.py
# Node command builder. Runs inside the shared session container.

from __future__ import annotations

import shlex

from app.src.infrastructure.sandbox.base_sandbox_adapter import BaseSandboxAdapter
from app.src.ports.outbound.sandbox_port import (
    ExecutionResult,
    SandboxLanguage,
    TestResult,
)


class NodeSandbox(BaseSandboxAdapter):
    language = SandboxLanguage.NODE

    def _code_command(self, file_name: str, args: list[str] | None) -> str:
        return f"node {shlex.quote(file_name)}{self._quote_args(args)}"

    def _test_command(self, target: str | None, framework: str) -> str:
        if target:
            return f"node --test {shlex.quote(target)}"
        return "node --test"

    def _lint_command(self, target: str | None, linter: str, fix: bool) -> str:
        command = f"eslint -f unix {shlex.quote(target or '.')}"
        if fix:
            command += " --fix"
        return command

    def _install_command(
        self, package: str, manager: str, version: str | None
    ) -> str:
        spec = f"{package}@{version}" if version else package
        return f"npm install --no-save {shlex.quote(spec)}"

    def _parse_tests(self, result: ExecutionResult) -> TestResult:
        text = f"{result.stdout}\n{result.stderr}"
        return TestResult(
            passed=self._count(r"#\s*pass\s+(\d+)", text),
            failed=self._count(r"#\s*fail\s+(\d+)", text),
            errors=self._count(r"#\s*cancelled\s+(\d+)", text),
            output=result.output,
            exit_code=result.exit_code,
        )
