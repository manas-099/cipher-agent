
# app/src/config/settings.py
# Single source of truth for all configuration.
# All other modules import from here — never read .env directly.

from __future__ import annotations

from functools import lru_cache
# pyrefly: ignore[missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── shared .env files (checked in order, first found wins) ────────────────────
_ENV_FILES = (".env", ".env.local", ".env.production")


# ── base class all setting groups inherit from ────────────────────────────────
class _EnvBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",          # silently ignore unknown env vars
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. LLM SETTINGS
# ─────────────────────────────────────────────────────────────────────────────




class OpenAISettings(_EnvBase):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="OPENAI_",
    )

    API_KEY:        str = ""
    MODEL_NAME:     str = "gpt-4o"
    MAX_TOKENS:     int = 4096
    TEMPERATURE:    float = 0.0
    TIMEOUT_SECONDS: int = 60
    MAX_RETRIES:    int = 3


class MyLLMSettings(_EnvBase):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MYLLM_",
    )

    API_URL:        str = ""
    AUTH_TOKEN:     str = ""
    MODEL_NAME:     str = ""
    TIMEOUT_SECONDS: int = 60
    MAX_RETRIES:    int = 3
    RETRY_DELAY_SECONDS: float = 2.0

    # Health-check behaviour (see infrastructure/llm/health.py):
    # on each generate() call the chain first checks a cached health flag
    # instead of always trying MyLLM cold. If MyLLM was last seen down, it is
    # skipped until COOLDOWN_SECONDS has passed since the last failed check.
    HEALTH_CHECK_ATTEMPTS:        int = 2
    HEALTH_CHECK_TIMEOUT_SECONDS: int = 10
    HEALTH_CHECK_COOLDOWN_SECONDS: int = 60


# ─────────────────────────────────────────────────────────────────────────────
# 2. API / SERVER SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

class APISettings(_EnvBase):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="API_",
    )

    HOST:           str = "0.0.0.0"
    PORT:           int = 8000
    DEBUG:          bool = False
    RELOAD:         bool = False

    # middleware
    RATE_LIMIT_PER_MINUTE:  int = 20
    REQUEST_TIMEOUT_SECONDS: int = 300     # 5 min max per agent task
    MAX_BODY_SIZE_BYTES:     int = 1_000_000  # 1 MB

    # CORS
    CORS_ORIGINS:   list[str] = ["http://localhost:8001"]
    CORS_METHODS:   list[str] = ["GET", "POST"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. SANDBOX / DOCKER SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

class SandboxSettings(_EnvBase):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="SANDBOX_",
    )

    TIMEOUT_SECONDS:    int = 30
    MEMORY_LIMIT_MB:    int = 256
    CPU_LIMIT:          float = 1.0
    NETWORK_DISABLED:   bool = True
    IMAGE_PYTHON:       str = "python:3.11-slim"
    IMAGE_NODE:         str = "node:20-slim"
    IMAGE_BASH:         str = "ubuntu:22.04"


# ─────────────────────────────────────────────────────────────────────────────
# 4. MODEL ROUTING SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

class RoutingSettings(_EnvBase):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="ROUTING_",
    )

    # which strategy to use:
    # complexity | cost | task_type | performance
    STRATEGY: str = "complexity"

    # complexity thresholds
    LOW_COMPLEXITY_MODEL:    str = "claude-haiku"
    MEDIUM_COMPLEXITY_MODEL: str = "claude-sonnet"
    HIGH_COMPLEXITY_MODEL:   str = "claude-opus"


# ─────────────────────────────────────────────────────────────────────────────
# 5. MASTER SETTINGS (aggregates all groups)
# ─────────────────────────────────────────────────────────────────────────────

class Settings:
    """
    Master settings object.

    """

    def __init__(self):
        self.openai    = OpenAISettings()
        self.my_llm    = MyLLMSettings()
        self.api       = APISettings()
        self.sandbox   = SandboxSettings()
        self.routing   = RoutingSettings()


# ─────────────────────────────────────────────────────────────────────────────
# 6. FACTORY METHOD  (this is the one everyone imports)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Factory method — creates Settings once, caches forever.

    lru_cache ensures:
      - .env is read exactly once at startup
      - every module gets the SAME Settings instance
      - no redundant disk reads or object creation

    
    """
    return Settings()