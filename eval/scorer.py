"""Scoring functions for comparing pipeline output against gold dossier expectations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from observability import count_empty_fields

logger = logging.getLogger("cdd_pipeline.eval")


@dataclass
class ScoreResult:
    """Aggregated evaluation scores for a single dossier run."""

    name: str
    passed: bool = True
    details: list[str] = field(default_factory=list)

    risico_match: bool = False
    senior_status_match: bool = False
    iteration_count: int = 0
    total_empty_fields: int = 0
    must_have_hits: int = 0
    must_have_total: int = 0
    must_not_violations: int = 0
    herkomst_hits: int = 0
    herkomst_total: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)

    def summary_line(self) -> str:
        pf = "PASS" if self.passed else "FAIL"
        return (
            f"[{pf}] {self.name} | risico={self.risico_match} | "
            f"status={self.senior_status_match} | "
            f"iterations={self.iteration_count} | "
            f"empty_fields={self.total_empty_fields} | "
            f"must_have={self.must_have_hits}/{self.must_have_total} | "
            f"herkomst={self.herkomst_hits}/{self.herkomst_total} | "
            f"violations={self.must_not_violations} | "
            f"tokens={self.token_usage.get('total_tokens', '?')} | "
            f"schema_failures={self.token_usage.get('schema_validation_failures', 0)}"
        )


def _extract_herkomst_sources(final_state: dict[str, Any]) -> list[str]:
    """Extract normalized herkomstbronnen from the Junior Herkomst section."""
    herkomst_sectie = final_state.get("herkomst_sectie") or {}
    herkomst_middelen = herkomst_sectie.get("herkomst_middelen") or {}
    antwoord = herkomst_middelen.get("antwoord", "")
    if not antwoord:
        return []

    raw_sources = re.split(r"[,;\n]|(?:\s+-\s+)", antwoord)
    return [source.strip().lower() for source in raw_sources if source.strip()]


def score_run(
    final_state: dict[str, Any],
    expected: dict[str, Any],
    name: str,
    token_summary: dict[str, int] | None = None,
) -> ScoreResult:
    """Compare a completed pipeline state against gold expectations.

    Args:
        final_state: The CddState dict after the graph finishes.
        expected: The ``"expected"`` block from a gold dossier JSON.
        name: Human-readable label for this dossier.
        token_summary: Optional output from ``TokenUsageHandler.summary()``.
    """
    result = ScoreResult(name=name)
    result.token_usage = token_summary or {}

    actual_risico = final_state.get("risicoclassificatie", "")
    expected_risico = expected.get("risicoclassificatie")
    if expected_risico:
        result.risico_match = actual_risico == expected_risico
        if not result.risico_match:
            result.passed = False
            result.details.append(
                f"Risicoclassificatie mismatch: expected={expected_risico}, got={actual_risico}"
            )

    actual_iterations = final_state.get("iteration_count", 0)
    result.iteration_count = actual_iterations
    max_iter = expected.get("max_iterations")
    if max_iter is not None and actual_iterations > max_iter:
        result.passed = False
        result.details.append(
            f"Iteration overshoot: expected<={max_iter}, got={actual_iterations}"
        )

    expected_status = expected.get("expected_senior_status")
    if expected_status:
        senior_review = final_state.get("senior_review", "")
        result.senior_status_match = expected_status in senior_review
        if not result.senior_status_match:
            result.passed = False
            result.details.append(
                f"Senior status mismatch: expected {expected_status} in senior_review"
            )

    total_empty = 0
    for label, key in [
        ("identificatie", "identificatie_sectie"),
        ("klantprofiel", "klantprofiel_sectie"),
        ("screening", "screening_sectie"),
        ("structuur_ubo", "structuur_ubo_sectie"),
        ("herkomst", "herkomst_sectie"),
        ("transactieprofiel", "transactieprofiel_sectie"),
    ]:
        total_empty += count_empty_fields(final_state.get(key), label)
    result.total_empty_fields = total_empty

    max_empty = expected.get("expected_empty_fields_max")
    if max_empty is not None and total_empty > max_empty:
        result.passed = False
        result.details.append(
            f"Too many empty fields: expected<={max_empty}, got={total_empty}"
        )

    actual_sources = _extract_herkomst_sources(final_state)
    expected_sources = expected.get("expected_herkomst_bronnen", [])
    result.herkomst_total = len(expected_sources)
    for source in expected_sources:
        if any(source.lower() in actual_source for actual_source in actual_sources):
            result.herkomst_hits += 1
        else:
            result.passed = False
            result.details.append(f"Missing expected herkomstbron: '{source}'")

    report = final_state.get("final_report", "")

    must_have = expected.get("must_have_facts", [])
    result.must_have_total = len(must_have)
    for fact in must_have:
        if re.search(re.escape(fact), report, re.IGNORECASE):
            result.must_have_hits += 1
        else:
            result.passed = False
            result.details.append(f"Missing required fact: '{fact}'")

    must_not = expected.get("must_not_have", [])
    for forbidden in must_not:
        if re.search(re.escape(forbidden), report, re.IGNORECASE):
            result.must_not_violations += 1
            result.passed = False
            result.details.append(f"Forbidden content found: '{forbidden}'")

    return result
