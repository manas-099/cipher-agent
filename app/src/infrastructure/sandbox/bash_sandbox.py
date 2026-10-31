# app/src/infrastructure/sandbox/bash_sandbox.py
# Bash command builder. Runs inside the shared session container.

from __future__ import annotations

import shlex

from app.src.infrastructure.sandbox.base_sandbox_adapter import BaseSandboxAdapter
from app.src.ports.outbound.sandbox_port import (
    ExecutionResult,
    SandboxLanguage,
    TestResult,
)


class BashSandbox(BaseSandboxAdapter):
    language = SandboxLanguage.BASH

    def _code_command(self, file_name: str, args: list[str] | None) -> str:
        return f"bash {shlex.quote(file_name)}{self._quote_args(args)}"

    def _test_command(self, target: str | None, framework: str) -> str:
        if target:
            return f"bash {shlex.quote(target)}"
        return "echo 'Bash sandbox: pass test_file to run a script'; exit 2"

    def _lint_command(self, target: str | None, linter: str, fix: bool) -> str:
        return "find . -name '*.sh' -print0 | xargs -0 -r -n1 bash -n"

    def _install_command(
        self, package: str, manager: str, version: str | None
    ) -> str:
        spec = f"{package}={version}" if version else package
        return f"apt-get update && apt-get install -y {shlex.quote(spec)}"

    def _parse_tests(self, result: ExecutionResult) -> TestResult:
        return TestResult(
            passed=1 if result.success else 0,
            failed=0 if result.success else 1,
            errors=0,
            output=result.output,
            exit_code=result.exit_code,
        )
