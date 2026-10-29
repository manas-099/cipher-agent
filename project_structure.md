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
│       │   │   │   ├── tool_executor_node.py           # executes tools
│       │   │   │   ├── file_reader_node.py             # handles file reading
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
│       │   └── models/                                # domain models (NOT LLM)
│       │       ├── chat_message.py                    # ChatMessage dataclass
│       │       ├── tool_call.py                       # ToolCall dataclass
│       │       ├── tool_result.py                     # ToolResult dataclass
│       │       └── agent_state.py                     # AgentState dataclass
│       │
│       │
│       ├── ports/                                     # CONTRACTS / INTERFACES
│       │   │                                          # domain defines what it needs
│       │   │                                          # infrastructure implements it
│       │   ├── i_llm_client.py                        # how domain talks to any LLM
│       │   ├── i_sandbox.py                           # how domain runs code
│       │   ├── i_file_system.py                       # how domain reads/writes files
│       │   ├── i_chat_service.py                      # how API talks to domain
│       │   └── i_agent_service.py                     # how agent is triggered
│       │
│       │
│       ├── application/                               # USE CASES
│       │   │                                          # orchestrates domain + ports
│       │   │                                          # one file per use case
│       │   ├── chat_service.py                        # implements i_chat_service
│       │   └── agent_service.py                       # implements i_agent_service
│       │
│       │
│       ├── api/                                       # INBOUND ADAPTER
│       │   │                                          # how outside world talks to app
│       │   │                                          # only FastAPI code lives here
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
│       │   │                                          # implements ports
│       │   │                                          # all external libs live here
│       │   │
│       │   ├── llm/                                   # LLM providers
│       │   │   ├── base_llm_adapter.py                # abstract base
│       │   │   ├── anthropic_adapter.py               # implements i_llm_client
│       │   │   ├── openai_adapter.py                  # implements i_llm_client
│       │   │   ├── llm_factory.py                     # LLMFactory
│       │   │   ├── llm_model_registry.py              # ModelRegistry
│       │   │   │                                      # stores model configs/costs
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
│       │   │   ├── python_sandbox.py                  # implements i_sandbox
│       │   │   ├── node_sandbox.py                    # implements i_sandbox
│       │   │   ├── bash_sandbox.py                    # implements i_sandbox
│       │   │   ├── sandbox_factory.py                 # SandboxFactory
│       │   │   ├── docker_runner.py                   # shared docker logic
│       │   │   └── Dockerfile.sandbox                 # sandbox image
│       │   │
│       │   └── filesystem/                            # file system access
│       │       └── local_fs_adapter.py                # implements i_file_system
│       │
│       │
│       ├── prompt_library/                            # PROMPTS
│       │   ├── system_prompt.txt
│       │   ├── planner_prompt.txt
│       │   └── verifier_prompt.txt
│       │
│       ├── config/                                    # CONFIGURATION
│       │   ├── model_config.py                        # model name, tokens, temp
│       │   ├── api_config.py                          # FastAPI, CORS, port
│       │   └── settings.py                            # loads .env, source of truth
│       │
│       ├── logger/
│       │   └── logger.py                              # structured logging
│       │
│       ├── exception/
│       │   └── exceptions.py                          # custom exceptions
│       │
│       └── main.py                                    # FastAPI app entry point
│
│
├── client/                                            # TERMINAL CLIENT
│   ├── chat.py                                        # chat interface
│   └── config.py                                      # backend URL, settings
│
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_tool_registry.py
│   │   │   ├── test_tool_factory.py
│   │   │   └── test_node_factory.py
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