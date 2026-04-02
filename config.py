"""Centralized configuration and LLM factory for the CDD application."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure Document Intelligence
    azure_doc_intel_endpoint: str
    azure_doc_intel_key: str

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-12-01-preview"

    # Azure Anthropic (Foundry / OpenAI endpoint) for Claude models
    azure_anthropic_endpoint: str | None = None

    # Model deployments
    heavy_deployment: str = "gpt-4o"
    light_deployment: str = "gpt-4o-mini"

    # Tuning
    max_senior_iterations: int = 3

    @field_validator("max_senior_iterations")
    @classmethod
    def _validate_max_iterations(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("max_senior_iterations must be between 1 and 10")
        return v

    @field_validator("azure_openai_endpoint", "azure_doc_intel_endpoint", "azure_anthropic_endpoint")
    @classmethod
    def _validate_endpoints(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("Endpoint must start with https://")
        return v

    @field_validator("azure_openai_api_key", "azure_doc_intel_key")
    @classmethod
    def _validate_api_keys(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("API key appears too short — check your .env file")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_heavy_llm() -> BaseChatModel:
    s = get_settings()
    
    if "claude" in s.heavy_deployment.lower():
        from langchain_anthropic import ChatAnthropic
        if not s.azure_anthropic_endpoint:
            raise ValueError("AZURE_ANTHROPIC_ENDPOINT must be set in .env for Claude models.")
        
        # Gebruik de Anthropic client maar verwijs deze naar Azure's proxy-URL
        # We gebruiken dezelfde API key als voor OpenAI
        return ChatAnthropic(
            model_name=s.heavy_deployment,
            anthropic_api_key=s.azure_openai_api_key,
            anthropic_api_url=s.azure_anthropic_endpoint,
            max_tokens=16384,
            temperature=0,
        )

    return AzureChatOpenAI(
        azure_deployment=s.heavy_deployment,
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        temperature=0,
    )


def get_light_llm() -> BaseChatModel:
    s = get_settings()
    
    if "claude" in s.light_deployment.lower():
        from langchain_anthropic import ChatAnthropic
        if not s.azure_anthropic_endpoint:
            raise ValueError("AZURE_ANTHROPIC_ENDPOINT must be set in .env for Claude models.")
        
        return ChatAnthropic(
            model_name=s.light_deployment,
            anthropic_api_key=s.azure_openai_api_key,
            anthropic_api_url=s.azure_anthropic_endpoint,
            max_tokens=16384,
            temperature=0,
        )

    return AzureChatOpenAI(
        azure_deployment=s.light_deployment,
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        temperature=0,
    )
