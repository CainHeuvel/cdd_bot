"""Lightweight observability: token usage logging and structured output quality metrics."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("cdd_pipeline.tokens")


class TokenUsageHandler(BaseCallbackHandler):
    """LangChain callback that logs token usage per LLM call.

    Attach via ``llm.invoke(messages, config={"callbacks": [handler]})``.
    Also accumulates totals for the lifetime of the handler instance.
    """

    def __init__(self) -> None:
        super().__init__()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        usage = (response.llm_output or {}).get("token_usage", {})
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)

        if prompt or completion:
            self.total_prompt_tokens += prompt
            self.total_completion_tokens += completion
            self.total_calls += 1

            model = (response.llm_output or {}).get("model_name", "unknown")
            logger.info(
                "LLM call | model=%s | prompt=%d | completion=%d | total=%d | cumulative_calls=%d",
                model, prompt, completion, total, self.total_calls,
            )

    def summary(self) -> dict[str, int]:
        return {
            "total_calls": self.total_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
        }


def count_empty_fields(section: dict | None, section_name: str) -> int:
    """Count required-but-empty fields in a structured Junior output section.

    Walks the dict looking for WerkbladVraag-shaped objects (dicts with an
    ``antwoord`` key) where ``antwoord`` is empty or None.  Returns the count
    and logs each occurrence.
    """
    if section is None:
        return 0

    empty = 0
    for field_name, value in section.items():
        if isinstance(value, dict) and "antwoord" in value:
            if not value["antwoord"]:
                empty += 1
                logger.warning(
                    "Empty antwoord | section=%s | field=%s",
                    section_name, field_name,
                )
        elif isinstance(value, dict):
            empty += count_empty_fields(value, f"{section_name}.{field_name}")
    return empty
