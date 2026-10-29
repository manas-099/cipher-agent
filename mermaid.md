graph LR
    subgraph Config
        Settings[Settings / .env]
    end

    subgraph Factory
        Factory[LLMClientFactory]
    end

    subgraph Domain ["Domain (Business Logic)"]
        Port["<<interface>>\nLLMPort"]
        Agent[Agent / Workflow Node]
    end

    subgraph Adapters ["Infrastructure (Adapters)"]
        MyLLM[MyLLMClient]
        Groq[GroqFallbackClient]
        OpenRouter[OpenRouterClient]
        Chain[LLMChain]
    end

    Settings --> Factory
    Factory -->|Instantiates & wires| MyLLM
    Factory -->|Instantiates & wires| Groq
    Factory -->|Instantiates & wires| OpenRouter
    Factory -->|Assembles| Chain

    MyLLM -.->|Implements| Port
    Groq -.->|Implements| Port
    OpenRouter -.->|Implements| Port
    Chain -.->|Implements| Port

    Agent -->|Consumes| Port
