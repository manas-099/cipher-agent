# app/src/config/model_config.py
# Static facts about LLM models — never changes per environment.
# ModelRegistry and RoutingStrategy import from here.

from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelSpec:
    name:                str
    provider:            str
    context_window:      int
    supports_tools:      bool
    supports_streaming:  bool
    input_cost_per_1k:   float   # USD per 1K input tokens
    output_cost_per_1k:  float   # USD per 1K output tokens


# ─────────────────────────────────────────────────────────────────────────────
# MODEL CONSTANTS  (use these instead of raw strings everywhere)
# ─────────────────────────────────────────────────────────────────────────────



MY_LLM         = "my-llm"


# ─────────────────────────────────────────────────────────────────────────────
# MODEL REGISTRY  (facts about each model)
# ─────────────────────────────────────────────────────────────────────────────

MODEL_SPECS: dict[str, ModelSpec] = {


    MY_LLM: ModelSpec(
        name               = MY_LLM,
        provider           = "my_llm",
        context_window     = 32_000,
        supports_tools     = False,
        supports_streaming = True,
        input_cost_per_1k  = 0.0,
        output_cost_per_1k = 0.0,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS  (used by ModelRegistry + RoutingStrategy)
# ─────────────────────────────────────────────────────────────────────────────

def get_spec(model_name: str) -> ModelSpec:
    if model_name not in MODEL_SPECS:
        raise ValueError(f"Unknown model: {model_name}")
    return MODEL_SPECS[model_name]


def get_context_window(model_name: str) -> int:
    return get_spec(model_name).context_window


def supports_tools(model_name: str) -> bool:
    return get_spec(model_name).supports_tools


def get_provider(model_name: str) -> str:
    return get_spec(model_name).provider


def cheapest_model() -> str:
    return min(
        MODEL_SPECS,
        key=lambda m: MODEL_SPECS[m].input_cost_per_1k
                    + MODEL_SPECS[m].output_cost_per_1k
    )


def models_by_provider(provider: str) -> list[str]:
    return [
        name for name, spec in MODEL_SPECS.items()
        if spec.provider == provider
    ]