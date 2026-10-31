# app/src/domain/tools/file_tools.py
# File and folder tools — 11 tools total.
# All call FilesystemPort — never touch os/pathlib directly.

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from app.src.domain.tools.base_tool import BaseTool, ToolOutput

if TYPE_CHECKING:
    from app.src.ports.outbound.filesystem_port import FilesystemPort


# ── 1. list_files ─────────────────────────────────────────────────────────────

class ListFilesTool(BaseTool):
    name        = "list_files"
    description = (
        "List all files inside a directory. "
        "Use recursive=true to walk all subdirectories."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"     : {"type": "string",  "description": "Directory path to list"},
                "recursive": {"type": "boolean", "description": "Walk subdirectories (default: false)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            files = self._fs.list_files(
                path      = args["path"],
                recursive = args.get("recursive", False),
            )
            content = "\n".join(files) if files else "No files found."
            return ToolOutput.ok(
                content = content,
                data    = {"path": args["path"], "files": files, "count": len(files)},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 2. read_file ──────────────────────────────────────────────────────────────

class ReadFileTool(BaseTool):
    name        = "read_file"
    description = (
        "Read the contents of a file. "
        "For large files use offset and limit for chunked reading. "
        "Always check has_more in the response — if True, read the next chunk."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"  : {"type": "string",  "description": "File path to read"},
                "offset": {"type": "integer", "description": "Line number to start from (default: 0)"},
                "limit" : {"type": "integer", "description": "Max lines to return (default: all)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            result = self._fs.read_file(
                path   = args["path"],
                offset = args.get("offset", 0),
                limit  = args.get("limit"),
            )
            content = (
                f"File: {result.path}\n"
                f"Lines: {result.total_lines} total"
                + (f" (showing from line {args.get('offset', 0)})" if args.get("offset") else "")
                + (f" | MORE CONTENT AVAILABLE — call read_file with offset={args.get('offset', 0) + (args.get('limit') or result.total_lines)}" if result.has_more else "")
                + f"\n\n{result.content}"
            )
            return ToolOutput.ok(
                content = content,
                data    = {
                    "path"       : result.path,
                    "total_lines": result.total_lines,
                    "has_more"   : result.has_more,
                    "size_bytes" : result.size_bytes,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 3. create_file ────────────────────────────────────────────────────────────

class CreateFileTool(BaseTool):
    name        = "create_file"
    description = (
        "Create a new file with given content. "
        "Fails if file already exists unless overwrite=true."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"     : {"type": "string",  "description": "File path to create"},
                "content"  : {"type": "string",  "description": "Content to write"},
                "overwrite": {"type": "boolean", "description": "Overwrite if exists (default: false)"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path", "content"]):
            return ToolOutput.error(err)
        try:
            self._fs.create_file(
                path      = args["path"],
                content   = args["content"],
                overwrite = args.get("overwrite", False),
            )
            return ToolOutput.ok(
                content = f"File created: {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 4. edit_file ──────────────────────────────────────────────────────────────

class EditFileTool(BaseTool):
    name        = "edit_file"
    description = (
        "Replace a block of lines in a file. "
        "Surgical block-level edit — not a full rewrite. "
        "Use replace_in_file for exact string replacement."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"       : {"type": "string",  "description": "File path to edit"},
                "start_line" : {"type": "integer", "description": "First line of block to replace (1-indexed)"},
                "end_line"   : {"type": "integer", "description": "Last line of block to replace (1-indexed)"},
                "new_content": {"type": "string",  "description": "New content to replace the block with"},
            },
            "required": ["path", "start_line", "end_line", "new_content"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path", "start_line", "end_line", "new_content"]):
            return ToolOutput.error(err)
        try:
            self._fs.edit_file(
                path        = args["path"],
                start_line  = args["start_line"],
                end_line    = args["end_line"],
                new_content = args["new_content"],
            )
            return ToolOutput.ok(
                content = f"Edited lines {args['start_line']}-{args['end_line']} in {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 5. replace_in_file ────────────────────────────────────────────────────────

class ReplaceInFileTool(BaseTool):
    name        = "replace_in_file"
    description = (
        "Find an exact string in a file and replace it. "
        "Fails if the string is not found or appears more than once "
        "and replace_all=false. Use for precise surgical edits."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"       : {"type": "string",  "description": "File path to edit"},
                "old_str"    : {"type": "string",  "description": "Exact string to find and replace"},
                "new_str"    : {"type": "string",  "description": "Replacement string"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default: false)"},
            },
            "required": ["path", "old_str", "new_str"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path", "old_str", "new_str"]):
            return ToolOutput.error(err)
        try:
            self._fs.replace_in_file(
                path        = args["path"],
                old_str     = args["old_str"],
                new_str     = args["new_str"],
                replace_all = args.get("replace_all", False),
            )
            return ToolOutput.ok(
                content = f"Replaced string in {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 6. delete_file ────────────────────────────────────────────────────────────

class DeleteFileTool(BaseTool):
    name        = "delete_file"
    description = "Permanently delete a file from the filesystem."

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"      : {"type": "string",  "description": "File path to delete"},
                "must_exist": {"type": "boolean", "description": "Raise error if file not found (default: true)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            self._fs.delete_file(
                path       = args["path"],
                must_exist = args.get("must_exist", True),
            )
            return ToolOutput.ok(
                content = f"Deleted file: {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 7. move_file ──────────────────────────────────────────────────────────────

class MoveFileTool(BaseTool):
    name        = "move_file"
    description = "Move or rename a file. Can move across directories."

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source"     : {"type": "string",  "description": "Current file path"},
                "destination": {"type": "string",  "description": "New file path"},
                "overwrite"  : {"type": "boolean", "description": "Overwrite destination if exists (default: false)"},
            },
            "required": ["source", "destination"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["source", "destination"]):
            return ToolOutput.error(err)
        try:
            self._fs.move_file(
                source      = args["source"],
                destination = args["destination"],
                overwrite   = args.get("overwrite", False),
            )
            return ToolOutput.ok(
                content = f"Moved {args['source']} → {args['destination']}",
                data    = {"source": args["source"], "destination": args["destination"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 8. copy_file ──────────────────────────────────────────────────────────────

class CopyFileTool(BaseTool):
    name        = "copy_file"
    description = (
        "Duplicate a file to a new path. "
        "Use as a safety backup before making edits."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source"     : {"type": "string",  "description": "File to copy"},
                "destination": {"type": "string",  "description": "Where to copy it"},
                "overwrite"  : {"type": "boolean", "description": "Overwrite destination if exists (default: false)"},
            },
            "required": ["source", "destination"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["source", "destination"]):
            return ToolOutput.error(err)
        try:
            self._fs.copy_file(
                source      = args["source"],
                destination = args["destination"],
                overwrite   = args.get("overwrite", False),
            )
            return ToolOutput.ok(
                content = f"Copied {args['source']} → {args['destination']}",
                data    = {"source": args["source"], "destination": args["destination"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 9. get_file_info ──────────────────────────────────────────────────────────

class GetFileInfoTool(BaseTool):
    name        = "get_file_info"
    description = (
        "Get file metadata without reading content. "
        "Use before read_file to check size and decide whether to chunk."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to inspect"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            info = self._fs.get_file_info(args["path"])
            content = (
                f"File: {info.path}\n"
                f"Exists: {info.exists}\n"
                f"Size: {info.size_kb:.1f} KB ({info.size_bytes} bytes)\n"
                f"Lines: {info.line_count}\n"
                f"Extension: {info.extension}\n"
                f"Last modified: {info.last_modified}"
            )
            return ToolOutput.ok(
                content = content,
                data    = {
                    "path"         : info.path,
                    "exists"       : info.exists,
                    "size_bytes"   : info.size_bytes,
                    "size_kb"      : info.size_kb,
                    "line_count"   : info.line_count,
                    "extension"    : info.extension,
                    "last_modified": info.last_modified,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 10. create_folder ─────────────────────────────────────────────────────────

class CreateFolderTool(BaseTool):
    name        = "create_folder"
    description = (
        "Create a new directory. "
        "Creates all intermediate directories if they do not exist."
    )

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"    : {"type": "string",  "description": "Directory path to create"},
                "exist_ok": {"type": "boolean", "description": "Do not raise if already exists (default: true)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            self._fs.create_folder(
                path     = args["path"],
                exist_ok = args.get("exist_ok", True),
            )
            return ToolOutput.ok(
                content = f"Folder created: {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))


# ── 11. delete_folder ─────────────────────────────────────────────────────────

class DeleteFolderTool(BaseTool):
    name        = "delete_folder"
    description = "Delete a directory and all its contents recursively."

    def __init__(self, fs: FilesystemPort) -> None:
        self._fs = fs

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path"      : {"type": "string",  "description": "Directory to delete"},
                "must_exist": {"type": "boolean", "description": "Raise error if not found (default: true)"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["path"]):
            return ToolOutput.error(err)
        try:
            self._fs.delete_folder(
                path       = args["path"],
                must_exist = args.get("must_exist", True),
            )
            return ToolOutput.ok(
                content = f"Deleted folder: {args['path']}",
                data    = {"path": args["path"]},
            )
        except Exception as e:
            return ToolOutput.error(str(e))