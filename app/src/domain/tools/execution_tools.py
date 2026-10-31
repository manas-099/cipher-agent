# app/src/domain/tools/execution_tools.py
# Execution tools — 5 tools total.
# All call SandboxPort — never touch Docker directly.

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from app.src.domain.tools.base_tool import BaseTool, ToolOutput
from app.src.ports.outbound.sandbox_port import SandboxLanguage

if TYPE_CHECKING:
    from app.src.ports.outbound.sandbox_port import SandboxPort


# ── 1. run_code ───────────────────────────────────────────────────────────────

class RunCodeTool(BaseTool):
    name        = "run_code"
    description = (
        "Run a code file inside an isolated Docker container. "
        "Supports Python, Node, and Bash. "
        "Container is destroyed after each run. Returns stdout, stderr, exit code."
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file to run"},
                "language" : {"type": "string", "enum": ["python", "node", "bash"], "description": "Runtime to use"},
                "timeout"  : {"type": "integer", "description": "Seconds before container is killed (default: 30)"},
                "args"     : {
                    "type" : "array",
                    "items": {"type": "string"},
                    "description": "Command line args to pass to the script",
                },
            },
            "required": ["file_path", "language"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["file_path", "language"]):
            return ToolOutput.error(err)
        try:
            result = self._sandbox.run_code(
                file_path = args["file_path"],
                language  = SandboxLanguage(args["language"]),
                timeout   = args.get("timeout", 30),
                args      = args.get("args"),
            )
            status  = "✓ Success" if result.success else "✗ Failed"
            content = (
                f"{status} (exit code: {result.exit_code}, {result.duration_seconds:.2f}s)\n\n"
                f"{result.output}"
            )
            return ToolOutput.ok(
                content = content,
                data    = {
                    "stdout"          : result.stdout,
                    "stderr"          : result.stderr,
                    "exit_code"       : result.exit_code,
                    "timed_out"       : result.timed_out,
                    "duration_seconds": result.duration_seconds,
                    "success"         : result.success,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 2. run_command ────────────────────────────────────────────────────────────

class RunCommandTool(BaseTool):
    name        = "run_command"
    description = (
        "Run a raw shell command inside Docker. "
        "Use for package installs, build commands, setup steps. "
        "Example: 'npm install', 'pip install requests', 'make build'."
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command"    : {"type": "string", "description": "Shell command to run"},
                "language"   : {"type": "string", "enum": ["python", "node", "bash"], "description": "Which Docker image to use"},
                "working_dir": {"type": "string", "description": "Directory to run command in (default: project root)"},
                "timeout"    : {"type": "integer", "description": "Seconds before kill (default: 30)"},
            },
            "required": ["command", "language"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["command", "language"]):
            return ToolOutput.error(err)
        try:
            result = self._sandbox.run_command(
                command     = args["command"],
                language    = SandboxLanguage(args["language"]),
                working_dir = args.get("working_dir"),
                timeout     = args.get("timeout", 30),
            )
            status  = "✓ Success" if result.success else "✗ Failed"
            content = (
                f"{status} (exit code: {result.exit_code}, {result.duration_seconds:.2f}s)\n\n"
                f"{result.output}"
            )
            return ToolOutput.ok(
                content = content,
                data    = {
                    "stdout"   : result.stdout,
                    "stderr"   : result.stderr,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "success"  : result.success,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 3. run_tests ──────────────────────────────────────────────────────────────

class RunTestsTool(BaseTool):
    name        = "run_tests"
    description = (
        "Run the test suite and return results. "
        "Supports pytest and jest. "
        "Use after making changes to verify nothing is broken."
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"     : {"type": "string", "description": "Directory to run tests in"},
                "framework": {"type": "string", "enum": ["pytest", "jest", "auto"], "description": "Test framework (default: auto)"},
                "test_file": {"type": "string", "description": "Run a specific test file only (default: all)"},
                "timeout"  : {"type": "integer", "description": "Seconds before kill (default: 60)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            result = self._sandbox.run_tests(
                path      = args["path"],
                framework = args.get("framework", "auto"),
                test_file = args.get("test_file"),
                timeout   = args.get("timeout", 60),
            )
            status  = "✓ All passed" if result.all_passed else "✗ Tests failed"
            content = (
                f"{status}\n"
                f"Passed: {result.passed} | Failed: {result.failed} | Errors: {result.errors}\n\n"
                f"{result.output}"
            )
            return ToolOutput.ok(
                content = content,
                data    = {
                    "passed"    : result.passed,
                    "failed"    : result.failed,
                    "errors"    : result.errors,
                    "all_passed": result.all_passed,
                    "total"     : result.total,
                    "exit_code" : result.exit_code,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 4. lint_code ──────────────────────────────────────────────────────────────

class LintCodeTool(BaseTool):
    name        = "lint_code"
    description = (
        "Run a linter on a file or directory and return errors and warnings. "
        "Use before run_code to catch issues early. "
        "Supports flake8 (Python) and eslint (JavaScript)."
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"  : {"type": "string",  "description": "File or directory to lint"},
                "linter": {"type": "string",  "enum": ["flake8", "eslint", "auto"], "description": "Linter to use (default: auto)"},
                "fix"   : {"type": "boolean", "description": "Auto-fix fixable issues (default: false)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            result = self._sandbox.lint_code(
                path   = args["path"],
                linter = args.get("linter", "auto"),
                fix    = args.get("fix", False),
            )
            status  = "✓ Clean" if result.clean else f"✗ {result.error_count} error(s), {result.warning_count} warning(s)"
            content = f"{status}\n\n{result.output}"
            return ToolOutput.ok(
                content = content,
                data    = {
                    "error_count"  : result.error_count,
                    "warning_count": result.warning_count,
                    "clean"        : result.clean,
                    "issues"       : [
                        {"file": i.file, "line": i.line, "column": i.column,
                         "message": i.message, "severity": i.severity}
                        for i in result.issues
                    ],
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 5. install_package ────────────────────────────────────────────────────────

class InstallPackageTool(BaseTool):
    name        = "install_package"
    description = (
        "Install a package inside the Docker sandbox. "
        "Use when code fails due to missing imports. "
        "Supports pip (Python) and npm (Node)."
    )

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Package name e.g. 'requests' or 'lodash'"},
                "manager": {"type": "string", "enum": ["pip", "npm", "auto"], "description": "Package manager (default: auto)"},
                "version": {"type": "string", "description": "Specific version e.g. '2.28.0' (default: latest)"},
            },
            "required": ["package"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["package"]):
            return ToolOutput.error(err)
        try:
            result = self._sandbox.install_package(
                package = args["package"],
                manager = args.get("manager", "auto"),
                version = args.get("version"),
            )
            status  = "✓ Installed" if result.success else "✗ Failed"
            content = f"{status}: {args['package']}\n\n{result.output}"
            return ToolOutput.ok(
                content = content,
                data    = {
                    "package"  : args["package"],
                    "success"  : result.success,
                    "exit_code": result.exit_code,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))