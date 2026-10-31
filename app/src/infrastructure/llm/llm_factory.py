# app/src/infrastructure/llm/llm_factory.py
# Creates and returns the correct LLM adapter instance.
# Application layer calls this once at startup.
# Nothing else ever imports concrete adapter classes directly.

from __future__ import annotations

from app.src.config.settings import get_settings
from app.src.infrastructure.llm.base_llm_adapter import BaseLLMAdapter
from app.src.infrastructure.llm.my_llm_adapter import LLMAdapter
from app.src.logger.logger import get_logger

logger = get_logger(__name__)


class LLMFactory:
    """
    Creates the correct LLM adapter based on settings.

    Currently only one adapter — LLMAdapter (self-hosted).
    When you add Groq or OpenRouter in Phase 2,
    add them here — nothing else changes.

    Usage:
        adapter = LLMFactory.create()
        # returns LLMAdapter instance, typed as BaseLLMAdapter
    """

    @staticmethod
    def create() -> BaseLLMAdapter:
        """
        Create and return the configured LLM adapter.
        Reads MYLLM_* settings to build the adapter.
        """
        settings = get_settings()

        logger.info(
            "llm_factory_creating_adapter",
            model   = settings.my_llm.MODEL_NAME,
            api_url = settings.my_llm.API_URL,
        )

        adapter = LLMAdapter()

        logger.info(
            "llm_factory_adapter_created",
            adapter  = adapter.__class__.__name__,
            provider = adapter.provider,
            model    = adapter.model_name,
        )

        return adapter