# app/src/domain/tools/search_tools.py
# Search tools — 3 tools total.
# grep_search, file_tree, find_and_replace_all.

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from app.src.domain.tools.base_tool import BaseTool, ToolOutput

if TYPE_CHECKING:
    from app.src.ports.outbound.filesystem_port import FilesystemPort


# ── 1. grep_search ────────────────────────────────────────────────────────────

class GrepSearchTool(BaseTool):
    name        = "grep_search"
    description = (
        "Search for a keyword or pattern across files in a directory. "
        "Returns filename, line number, and matching line content. "
        "Use this to find where a function, variable, or string is used."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"          : {"type": "string",  "description": "Directory to search in"},
                "pattern"       : {"type": "string",  "description": "String or regex pattern to search for"},
                "file_pattern"  : {"type": "string",  "description": "Glob filter e.g. '*.py' (default: all files)"},
                "recursive"     : {"type": "boolean", "description": "Search subdirectories (default: true)"},
                "case_sensitive": {"type": "boolean", "description": "Case sensitive search (default: true)"},
                "max_results"   : {"type": "integer", "description": "Cap results (default: 100)"},
            },
            "required": ["path", "pattern"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path", "pattern"]):
            return ToolOutput.error(err)
        try:
            matches = self._fs.grep_search(
                path           = args["path"],
                pattern        = args["pattern"],
                file_pattern   = args.get("file_pattern", "*"),
                recursive      = args.get("recursive", True),
                case_sensitive = args.get("case_sensitive", True),
                max_results    = args.get("max_results", 100),
            )
            if not matches:
                return ToolOutput.ok(
                    content = f"No matches found for '{args['pattern']}'",
                    data    = {"matches": [], "count": 0},
                )

            lines = [
                f"{m.file}:{m.line_number}: {m.line_content.strip()}"
                for m in matches
            ]
            content = f"Found {len(matches)} match(es) for '{args['pattern']}':\n\n" + "\n".join(lines)

            return ToolOutput.ok(
                content = content,
                data    = {
                    "matches": [
                        {"file": m.file, "line_number": m.line_number, "line_content": m.line_content}
                        for m in matches
                    ],
                    "count": len(matches),
                    "path" : args["path"],
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 2. file_tree ──────────────────────────────────────────────────────────────

class FileTreeTool(BaseTool):
    name        = "file_tree"
    description = (
        "Return the directory structure as a tree. "
        "No file content — structure only. Very fast and low token cost. "
        "Always call this first when exploring a new codebase."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"       : {"type": "string",  "description": "Root directory to tree"},
                "max_depth"  : {"type": "integer", "description": "How deep to go (default: 3)"},
                "show_hidden": {"type": "boolean", "description": "Include dotfiles (default: false)"},
                "ignore"     : {
                    "type" : "array",
                    "items": {"type": "string"},
                    "description": "Folders to skip e.g. ['node_modules', '.git']",
                },
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            tree = self._fs.file_tree(
                path        = args["path"],
                max_depth   = args.get("max_depth", 3),
                show_hidden = args.get("show_hidden", False),
                ignore      = args.get("ignore"),
            )
            return ToolOutput.ok(
                content = tree,
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 3. find_and_replace_all ───────────────────────────────────────────────────

class FindAndReplaceAllTool(BaseTool):
    name        = "find_and_replace_all"
    description = (
        "Find a string across multiple files and replace it everywhere. "
        "Use for renaming functions, variables, class names across a codebase. "
        "Use dry_run=true first to see what would change."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"        : {"type": "string",  "description": "Root directory to search in"},
                "old_str"     : {"type": "string",  "description": "Exact string to find"},
                "new_str"     : {"type": "string",  "description": "Replacement string"},
                "file_pattern": {"type": "string",  "description": "Glob filter e.g. '*.py' (default: all files)"},
                "recursive"   : {"type": "boolean", "description": "Search subdirectories (default: true)"},
                "dry_run"     : {"type": "boolean", "description": "Show matches but do not change anything (default: false)"},
            },
            "required": ["path", "old_str", "new_str"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path", "old_str", "new_str"]):
            return ToolOutput.error(err)
        try:
            result = self._fs.find_and_replace_all(
                path         = args["path"],
                old_str      = args["old_str"],
                new_str      = args["new_str"],
                file_pattern = args.get("file_pattern", "*"),
                recursive    = args.get("recursive", True),
                dry_run      = args.get("dry_run", False),
            )
            dry_run = args.get("dry_run", False)
            total   = sum(result.values())

            if not result:
                return ToolOutput.ok(
                    content = f"No matches found for '{args['old_str']}'",
                    data    = {"files_changed": {}, "total_replacements": 0},
                )

            lines = [f"  {file}: {count} replacement(s)" for file, count in result.items()]
            action  = "Would change" if dry_run else "Changed"
            content = (
                f"{action} {len(result)} file(s), {total} replacement(s) total"
                + (" [DRY RUN — no files changed]" if dry_run else "")
                + ":\n" + "\n".join(lines)
            )

            return ToolOutput.ok(
                content = content,
                data    = {"files_changed": result, "total_replacements": total, "dry_run": dry_run},
            )
        except Exception as e:
            return ToolOutput.error(str(e))