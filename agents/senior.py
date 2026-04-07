"""Senior Agent — Compliance Officer validator (heavy model)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm, get_settings
from prompts.system_prompts import SENIOR_PROMPT


def _format_sectie(label: str, sectie: dict | None) -> str:
    """Format a Pydantic dict section as readable JSON for LLM consumption."""
    if sectie is None:
        return f"### {label}\n[GEEN OUTPUT]\n"
    return f"### {label}\n```json\n{json.dumps(sectie, indent=2, ensure_ascii=False)}\n```\n"


def _extract_status(content: str) -> str | None:
    """Read the explicit Senior status line without substring false positives."""
    match = re.search(r"^\*\*Status\*\*:\s*(GOEDGEKEURD|AFGEKEURD)\b", content, re.IGNORECASE | re.MULTILINE)
    return match.group(1).upper() if match else None


def senior_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Validate Junior outputs against Wwft policy; approve or return feedback.

    Reads: all junior outputs, recon_index, analyst_feedback, senior_feedback, iteration_count
    Writes: senior_approved, senior_feedback, iteration_count, current_agent
    """
    iteration = state.get("iteration_count", 0) + 1
    max_iterations = get_settings().max_senior_iterations
    analyst_feedback: list[str] = state.get("analyst_feedback", [])
    prior_senior_feedback: list[str] = state.get("senior_feedback", [])

    # Build structured overview of all junior outputs
    secties = (
        _format_sectie("Identificatie & Verificatie", state.get("identificatie_sectie"))
        + _format_sectie("Klantprofiel", state.get("klantprofiel_sectie"))
        + _format_sectie("Screening", state.get("screening_sectie"))
        + _format_sectie("Structuur & UBO", state.get("structuur_ubo_sectie"))
        + _format_sectie("Herkomst van Middelen", state.get("herkomst_sectie"))
        + _format_sectie("Transactieprofiel", state.get("transactieprofiel_sectie"))
    )

    user_content = (
        f"## Iteratie {iteration} van maximaal {max_iterations}\n\n"
        f"## Client type\n{state['client_type']}\n\n"
        f"## Toelichting analist\n{state['toelichting']}\n\n"
        f"## Document-index (Recon Agent)\n{state['recon_index']}\n\n"
        f"## Gestructureerde output Junior Agents\n\n{secties}\n"
    )

    if analyst_feedback:
        user_content += (
            "## Feedback van de analist\n"
            + "\n".join(f"- {fb}" for fb in analyst_feedback)
            + "\n\n"
        )

    if prior_senior_feedback:
        user_content += (
            "## Eerdere feedback van de Senior Agent\n"
            + "\n".join(f"- {fb}" for fb in prior_senior_feedback)
            + "\n\n"
        )

    if iteration >= max_iterations:
        user_content += (
            "**LET OP**: Dit is de laatste iteratie. Keur het rapport goed, "
            "maar benoem alle resterende gaps expliciet zodat het Report Agent "
            "deze als ONTBREKEND kan markeren.\n"
        )

    llm = get_heavy_llm()
    response = llm.invoke([
        SystemMessage(content=SENIOR_PROMPT),
        HumanMessage(content=user_content),
    ])

    content: str = response.content
    status = _extract_status(content)
    approved = status == "GOEDGEKEURD" or iteration >= max_iterations

    feedback_items: list[str] = []
    if not approved:
        feedback_items = [content]

    # Parse risicoclassificatie from Senior output
    risico_match = re.search(
        r"\*\*Risicoclassificatie\*\*:\s*(Laag|Medium|Verhoogd|Onacceptabel)",
        content,
        re.IGNORECASE,
    )
    risicoclassificatie = risico_match.group(1) if risico_match else ""

    return {
        "senior_approved": approved,
        "senior_feedback": feedback_items,
        "iteration_count": iteration,
        "senior_review": content,
        "risicoclassificatie": risicoclassificatie,
        "current_agent": "senior",
    }
