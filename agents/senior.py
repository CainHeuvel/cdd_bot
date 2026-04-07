"""Senior Agent — Compliance Officer validator (heavy model)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm, get_settings
from models.agent_contracts import SeniorDecision
from prompts.system_prompts import SENIOR_PROMPT

logger = logging.getLogger(__name__)


def _format_sectie(label: str, sectie: dict | None) -> str:
    """Format a Pydantic dict section as readable JSON for LLM consumption."""
    if sectie is None:
        return f"### {label}\n[GEEN OUTPUT]\n"
    return f"### {label}\n```json\n{json.dumps(sectie, indent=2, ensure_ascii=False)}\n```\n"


def senior_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Validate Junior outputs against Wwft policy; approve or return feedback.

    Reads: all junior outputs, recon_index, analyst_feedback, senior_feedback, iteration_count
    Writes: senior_approved, senior_feedback, senior_feedback_structuur, senior_feedback_herkomst,
            senior_feedback_vermogen, iteration_count, senior_review, risicoclassificatie, current_agent
    """
    iteration = state.get("iteration_count", 0) + 1
    max_iterations = get_settings().max_senior_iterations
    analyst_feedback: list[str] = state.get("analyst_feedback", [])
    prior_senior_feedback: list[str] = state.get("senior_feedback", [])

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
            "**LET OP**: Dit is de laatste iteratie. Zet status op GOEDGEKEURD, "
            "maar benoem alle resterende gaps in remaining_gaps zodat het Report Agent "
            "deze als ONTBREKEND kan markeren.\n"
        )

    llm = get_heavy_llm()
    structured_llm = llm.with_structured_output(SeniorDecision)
    decision: SeniorDecision = structured_llm.invoke([
        SystemMessage(content=SENIOR_PROMPT),
        HumanMessage(content=user_content),
    ])

    approved = decision.status == "GOEDGEKEURD" or iteration >= max_iterations

    feedback_items: list[str] = []
    for fb in [
        decision.feedback_structuur,
        decision.feedback_herkomst,
        decision.feedback_vermogen,
        decision.feedback_algemeen,
    ]:
        if fb:
            feedback_items.append(fb)

    senior_review = (
        f"**Status**: {decision.status}\n\n"
        f"**Risicoclassificatie**: {decision.risicoclassificatie}\n"
        f"**Onderbouwing**: {decision.onderbouwing_classificatie}\n"
    )
    if decision.remaining_gaps:
        senior_review += "\n**Resterende gaps**:\n" + "\n".join(
            f"- {g}" for g in decision.remaining_gaps
        )

    logger.info(
        "Senior decision | iteration=%d | status=%s | risico=%s | gaps=%d | feedback_items=%d",
        iteration, decision.status, decision.risicoclassificatie,
        len(decision.remaining_gaps), len(feedback_items),
    )

    return {
        "senior_approved": approved,
        "senior_feedback": feedback_items,
        "senior_feedback_structuur": decision.feedback_structuur or "",
        "senior_feedback_herkomst": decision.feedback_herkomst or "",
        "senior_feedback_vermogen": decision.feedback_vermogen or "",
        "iteration_count": iteration,
        "senior_review": senior_review,
        "senior_onderbouwing_classificatie": decision.onderbouwing_classificatie,
        "risicoclassificatie": decision.risicoclassificatie,
        "current_agent": "senior",
    }
