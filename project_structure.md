```text

cipher-agent/
│
├── app/
│   └── src/
│       │
│       ├── domain/                                    # CORE BUSINESS LOGIC
│       │   │                                          # pure Python, zero external imports
│       │   │
│       │   ├── agent/
│       │   │   ├── nodes/
│       │   │   │   ├── base_node.py                   # abstract base node
│       │   │   │   ├── planner_node.py                # plans the task
│       │   │   │   ├── tool_executor_node.py          # executes tools
│       │   │   │   ├── file_reader_node.py            # handles file reading
│       │   │   │   └── verifier_node.py               # runs + checks output
│       │   │   ├── node_factory.py                    # NodeFactory
│       │   │   ├── node_registry.py                   # NodeRegistry
│       │   │   ├── graph_builder.py                   # builds langgraph graph
│       │   │   └── agent.py                           # agent entry point
│       │   │
│       │   ├── tools/
│       │   │   ├── base_tool.py                       # abstract BaseTool
│       │   │   ├── file_tools.py                      # read,create,edit,delete
│       │   │   ├── search_tools.py                    # grep, file_tree
│       │   │   ├── execution_tools.py                 # run_code, run_command
│       │   │   ├── tool_factory.py                    # ToolFactory
│       │   │   └── tool_registry.py                   # ToolRegistry
│       │   │
│       │   ├── memory/                                # MEMORY DOMAIN MODELS
│       │   │   ├── working_memory.py                  # AgentState during task
│       │   │   │                                      # files read, tool results
│       │   │   │                                      # current plan, task context
│       │   │   └── procedural_memory.py               # prompt loader
│       │   │                                          # loads from prompt_library/
│       │   │                                          # agent's HOW-TO knowledge
│       │   │
│       │   └── models/                                # DOMAIN DATA MODELS
│       │       ├── chat_message.py                    # ChatMessage dataclass
│       │       ├── tool_call.py                       # ToolCall dataclass
│       │       ├── tool_result.py                     # ToolResult dataclass
│       │       └── agent_state.py                     # AgentState dataclass
│       │                                              # (working memory state)
│       │
│       │
│       ├── ports/                                     # CONTRACTS / INTERFACES
│       │   │
│       │   ├── outbound/                              # domain → outside world
│       │   │   ├── llm_port.py                        # how domain talks to any LLM
│       │   │   ├── sandbox_port.py                    # how domain runs code
│       │   │   └── filesystem_port.py                 # how domain reads/writes files
│       │   │
│       │   └── inbound/                               # outside world → domain
│       │       ├── chat_service_port.py               # how API triggers chat
│       │       └── agent_service_port.py              # how API triggers agent
│       │
│       │
│       ├── application/                               # USE CASES
│       │   ├── chat_service.py                        # implements chat_service_port
│       │   └── agent_service.py                       # implements agent_service_port
│       │
│       │
│       ├── api/                                       # INBOUND ADAPTER
│       │   ├── routes/
│       │   │   ├── chat.py                            # POST /chat
│       │   │   └── health.py                          # GET /health
│       │   ├── dto/
│       │   │   ├── request.py                         # ChatRequest  (Pydantic)
│       │   │   └── response.py                        # ChatResponse (Pydantic)
│       │   └── middleware/
│       │       ├── request_id.py                      # generates request ID
│       │       ├── request_logger.py                  # logs every request
│       │       ├── error_handler.py                   # global exception → clean JSON
│       │       ├── rate_limiter.py                    # max requests per minute
│       │       ├── timeout.py                         # kills hung agent loops
│       │       ├── cors.py                            # CORS headers
│       │       ├── security_headers.py                # XSS, clickjacking protection
│       │       ├── body_size_limiter.py               # rejects huge payloads
│       │       └── context_injector.py                # injects logger, settings, ID
│       │
│       │
│       ├── infrastructure/                            # OUTBOUND ADAPTERS
│       │   │
│       │   ├── llm/                                   # LLM providers
│       │   │   ├── base_llm_adapter.py                # abstract base
│       │   │   ├── anthropic_adapter.py               # implements llm_port
│       │   │   ├── openai_adapter.py                  # implements llm_port
│       │   │   ├── llm_factory.py                     # LLMFactory
│       │   │   ├── llm_model_registry.py              # ModelRegistry
│       │   │   └── routing/                           # Strategy Pattern
│       │   │       ├── base_routing_strategy.py       # abstract base strategy
│       │   │       ├── complexity_strategy.py         # route by task complexity
│       │   │       ├── cost_strategy.py               # always cheapest model
│       │   │       ├── task_type_strategy.py          # route by task type
│       │   │       ├── performance_strategy.py        # always best model
│       │   │       └── strategy_registry.py           # StrategyRegistry
│       │   │
│       │   ├── sandbox/                               # code execution
│       │   │   ├── base_sandbox_adapter.py            # abstract base
│       │   │   ├── python_sandbox.py                  # implements sandbox_port
│       │   │   ├── node_sandbox.py                    # implements sandbox_port
│       │   │   ├── bash_sandbox.py                    # implements sandbox_port
│       │   │   ├── sandbox_factory.py                 # SandboxFactory
│       │   │   ├── docker_runner.py                   # shared docker logic
│       │   │   └── Dockerfile.sandbox                 # sandbox image
│       │   │
│       │   └── filesystem/                            # file system access
│       │       └── local_fs_adapter.py                # implements filesystem_port
│       │
│       │
│       ├── prompt_library/                            # PROCEDURAL MEMORY STORE
│       │   │                                          # agent's HOW-TO knowledge
│       │   │                                          # loaded by procedural_memory.py
│       │   ├── system_prompt.txt                      # main agent behaviour
│       │   ├── planner_prompt.txt                     # how to plan a task
│       │   └── verifier_prompt.txt                    # how to verify output
│       │
│       │
│       ├── config/                                    # CONFIGURATION
│       │   ├── model_config.py                        # model name, tokens, temp
│       │   ├── api_config.py                          # FastAPI, CORS, port
│       │   └── settings.py                            # loads .env, source of truth
│       │
│       │
│       ├── logger/
│       │   └── logger.py                              # structured logging
│       │
│       │
│       ├── exception/
│       │   └── exceptions.py                          # custom exceptions
│       │
│       │
│       └── main.py                                    # FastAPI app entry point
│
│
├── client/                                            # TERMINAL CLIENT
│   ├── chat.py                                        # terminal chat interface
│   └── config.py                                      # backend URL, settings
│
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_tool_registry.py
│   │   │   ├── test_tool_factory.py
│   │   │   ├── test_node_factory.py
│   │   │   └── test_working_memory.py
│   │   ├── infrastructure/
│   │   │   ├── test_anthropic_adapter.py
│   │   │   ├── test_docker_runner.py
│   │   │   └── test_routing_strategies.py
│   │   └── application/
│   │       └── test_chat_service.py
│   └── integration/
│       └── test_agent_flow.py
│
│
├── evals/
│   ├── test_cases/
│   │   ├── create_calculator.json
│   │   ├── fix_bug.json
│   │   └── refactor_code.json
│   └── run_evals.py
│
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── docker-compose.yml
└── README.md





```

