"""
cipher-agent project scaffolder
Run from INSIDE the cipher-agent folder:
    python scaffold.py

- Skips files/folders that already exist
- Never overwrites anything
- Only creates what is missing
"""

import os

# ── base is wherever you run the script from ──────────────────────────────────
BASE = os.getcwd()

# ── every file that should exist (relative to BASE) ───────────────────────────
FILES = [
    # ── domain / agent ────────────────────────────────────────────────────────
    "app/src/domain/agent/nodes/base_node.py",
    "app/src/domain/agent/nodes/planner_node.py",
    "app/src/domain/agent/nodes/tool_executor_node.py",
    "app/src/domain/agent/nodes/file_reader_node.py",
    "app/src/domain/agent/nodes/verifier_node.py",
    "app/src/domain/agent/node_factory.py",
    "app/src/domain/agent/node_registry.py",
    "app/src/domain/agent/graph_builder.py",
    "app/src/domain/agent/agent.py",

    # ── domain / tools ────────────────────────────────────────────────────────
    "app/src/domain/tools/base_tool.py",
    "app/src/domain/tools/file_tools.py",
    "app/src/domain/tools/search_tools.py",
    "app/src/domain/tools/execution_tools.py",
    "app/src/domain/tools/tool_factory.py",
    "app/src/domain/tools/tool_registry.py",

    # ── domain / memory ───────────────────────────────────────────────────────
    "app/src/domain/memory/working_memory.py",
    "app/src/domain/memory/procedural_memory.py",

    # ── domain / models ───────────────────────────────────────────────────────
    "app/src/domain/models/chat_message.py",
    "app/src/domain/models/tool_call.py",
    "app/src/domain/models/tool_result.py",
    "app/src/domain/models/agent_state.py",

    # ── ports / outbound ──────────────────────────────────────────────────────
    "app/src/ports/outbound/llm_port.py",
    "app/src/ports/outbound/sandbox_port.py",
    "app/src/ports/outbound/filesystem_port.py",

    # ── ports / inbound ───────────────────────────────────────────────────────
    "app/src/ports/inbound/chat_service_port.py",
    "app/src/ports/inbound/agent_service_port.py",

    # ── application ───────────────────────────────────────────────────────────
    "app/src/application/chat_service.py",
    "app/src/application/agent_service.py",

    # ── api / routes ──────────────────────────────────────────────────────────
    "app/src/api/routes/chat.py",
    "app/src/api/routes/health.py",

    # ── api / dto ─────────────────────────────────────────────────────────────
    "app/src/api/dto/request.py",
    "app/src/api/dto/response.py",

    # ── api / middleware ──────────────────────────────────────────────────────
    "app/src/api/middleware/request_id.py",
    "app/src/api/middleware/request_logger.py",
    "app/src/api/middleware/error_handler.py",
    "app/src/api/middleware/rate_limiter.py",
    "app/src/api/middleware/timeout.py",
    "app/src/api/middleware/cors.py",
    "app/src/api/middleware/security_headers.py",
    "app/src/api/middleware/body_size_limiter.py",
    "app/src/api/middleware/context_injector.py",

    # ── infrastructure / llm ──────────────────────────────────────────────────
    "app/src/infrastructure/llm/base_llm_adapter.py",
    "app/src/infrastructure/llm/anthropic_adapter.py",
    "app/src/infrastructure/llm/openai_adapter.py",
    "app/src/infrastructure/llm/llm_factory.py",
    "app/src/infrastructure/llm/llm_model_registry.py",

    # ── infrastructure / llm / routing ────────────────────────────────────────
    "app/src/infrastructure/llm/routing/base_routing_strategy.py",
    "app/src/infrastructure/llm/routing/complexity_strategy.py",
    "app/src/infrastructure/llm/routing/cost_strategy.py",
    "app/src/infrastructure/llm/routing/task_type_strategy.py",
    "app/src/infrastructure/llm/routing/performance_strategy.py",
    "app/src/infrastructure/llm/routing/strategy_registry.py",

    # ── infrastructure / sandbox ──────────────────────────────────────────────
    "app/src/infrastructure/sandbox/base_sandbox_adapter.py",
    "app/src/infrastructure/sandbox/python_sandbox.py",
    "app/src/infrastructure/sandbox/node_sandbox.py",
    "app/src/infrastructure/sandbox/bash_sandbox.py",
    "app/src/infrastructure/sandbox/sandbox_factory.py",
    "app/src/infrastructure/sandbox/docker_runner.py",
    "app/src/infrastructure/sandbox/Dockerfile.sandbox",

    # ── infrastructure / filesystem ───────────────────────────────────────────
    "app/src/infrastructure/filesystem/local_fs_adapter.py",

    # ── prompt library ────────────────────────────────────────────────────────
    "app/src/prompt_library/system_prompt.txt",
    "app/src/prompt_library/planner_prompt.txt",
    "app/src/prompt_library/verifier_prompt.txt",

    # ── config ────────────────────────────────────────────────────────────────
    "app/src/config/model_config.py",
    "app/src/config/api_config.py",
    "app/src/config/settings.py",

    # ── logger / exception / main ─────────────────────────────────────────────
    "app/src/logger/logger.py",
    "app/src/exception/exceptions.py",
    "app/src/main.py",

    # ── client ────────────────────────────────────────────────────────────────
    "client/chat.py",
    "client/config.py",

    # ── tests ─────────────────────────────────────────────────────────────────
    "tests/unit/domain/test_tool_registry.py",
    "tests/unit/domain/test_tool_factory.py",
    "tests/unit/domain/test_node_factory.py",
    "tests/unit/domain/test_working_memory.py",
    "tests/unit/infrastructure/test_anthropic_adapter.py",
    "tests/unit/infrastructure/test_docker_runner.py",
    "tests/unit/infrastructure/test_routing_strategies.py",
    "tests/unit/application/test_chat_service.py",
    "tests/integration/test_agent_flow.py",

    # ── evals ─────────────────────────────────────────────────────────────────
    "evals/test_cases/create_calculator.json",
    "evals/test_cases/fix_bug.json",
    "evals/test_cases/refactor_code.json",
    "evals/run_evals.py",

    # ── root ──────────────────────────────────────────────────────────────────
    ".env.example",
    ".gitignore",
    "docker-compose.yml",
]

# ── minimal starter content for key file types ────────────────────────────────
STARTERS = {
    ".py": "# TODO: implement\n",
    ".txt": "",
    ".md": "",
    ".json": "{}\n",
    ".yml": "",
    ".example": "",
    "Dockerfile.sandbox": "FROM python:3.11-slim\nWORKDIR /code\n",
}

def starter_content(filename: str) -> str:
    # check full filename first (e.g. Dockerfile.sandbox)
    base = os.path.basename(filename)
    if base in STARTERS:
        return STARTERS[base]
    # then check extension
    _, ext = os.path.splitext(filename)
    return STARTERS.get(ext, "")

def scaffold():
    created_dirs  = 0
    created_files = 0
    skipped       = 0

    for relative_path in FILES:
        full_path = os.path.join(BASE, relative_path)
        directory = os.path.dirname(full_path)

        # ── create folder if missing ──────────────────────────────────────────
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"  📁 created  {directory.replace(BASE, '').lstrip(os.sep)}")
            created_dirs += 1

            # drop __init__.py into every new Python package folder
            if not relative_path.startswith(("tests/", "evals/", "client/")):
                init = os.path.join(directory, "__init__.py")
                if not os.path.exists(init):
                    open(init, "w").close()

        # ── create file if missing ────────────────────────────────────────────
        if not os.path.exists(full_path):
            with open(full_path, "w") as f:
                f.write(starter_content(relative_path))
            print(f"  ✅ created  {relative_path}")
            created_files += 1
        else:
            print(f"  ⏭️  exists   {relative_path}")
            skipped += 1

    print()
    print("─" * 52)
    print(f"  📁 folders created : {created_dirs}")
    print(f"  ✅ files created   : {created_files}")
    print(f"  ⏭️  files skipped   : {skipped}  (already existed)")
    print("─" * 52)
    print("  Done. Run: cd cipher-agent && code .")

if __name__ == "__main__":
    print(f"\n🔨 Scaffolding cipher-agent into: {BASE}\n")
    scaffold()