"""Lightweight observability for token usage and schema quality."""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar, Token
import logging
from typing import Any, TypeVar
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.exceptions import OutputParserException
from langchain_core.outputs import LLMResult
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("cdd_pipeline.tokens")
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class RunObservability:
    """Per-run metrics container shared across the graph execution."""

    def __init__(self) -> None:
        self.token_handler = TokenUsageHandler()
        self.schema_failures: Counter[str] = Counter()

    def record_schema_failure(self, node_name: str, schema_name: str) -> None:
        self.schema_failures[f"{node_name}:{schema_name}"] += 1

    def summary(self) -> dict[str, Any]:
        summary = self.token_handler.summary()
        summary["schema_validation_failures"] = sum(self.schema_failures.values())
        summary["schema_validation_failures_by_node"] = dict(self.schema_failures)
        return summary


_ACTIVE_RUN: ContextVar[RunObservability | None] = ContextVar(
    "cdd_pipeline_active_run",
    default=None,
)


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


def activate_run_observability(run: RunObservability) -> Token[RunObservability | None]:
    """Activate a run-level observability context for the current thread."""
    return _ACTIVE_RUN.set(run)


def deactivate_run_observability(token: Token[RunObservability | None]) -> None:
    """Reset the current thread's run-level observability context."""
    _ACTIVE_RUN.reset(token)


def record_schema_failure(node_name: str, schema_name: str, exc: Exception) -> None:
    """Log and count a structured-output validation failure."""
    logger.warning(
        "Schema validation failed | node=%s | schema=%s | error=%s",
        node_name,
        schema_name,
        exc,
    )
    active_run = _ACTIVE_RUN.get()
    if active_run is not None:
        active_run.record_schema_failure(node_name, schema_name)


def invoke_structured(
    node_name: str,
    llm: Any,
    schema: type[SchemaT],
    messages: list[Any],
) -> SchemaT:
    """Invoke a model with structured output and track schema failures."""
    structured_llm = llm.with_structured_output(schema)
    try:
        return structured_llm.invoke(messages)
    except (ValidationError, OutputParserException) as exc:
        record_schema_failure(node_name, schema.__name__, exc)
        raise


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
