"""Senior Agent — Compliance Officer validator (heavy model)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm, get_settings
from prompts.system_prompts import SENIOR_PROMPT


def senior_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Validate Junior outputs against Wwft policy; approve or return feedback.

    Reads: all junior outputs, recon_index, iteration_count
    Writes: senior_approved, senior_feedback, iteration_count, current_agent
    """
    iteration = state.get("iteration_count", 0) + 1
    max_iterations = get_settings().max_senior_iterations

    user_content = (
        f"## Iteratie {iteration} van maximaal {max_iterations}\n\n"
        f"## Client type\n{state['client_type']}\n\n"
        f"## Toelichting analist\n{state['toelichting']}\n\n"
        f"## Document-index (Recon Agent)\n{state['recon_index']}\n\n"
        f"## Output Junior Structuur\n{state.get('klantprofiel', '[GEEN OUTPUT]')}\n\n"
        f"## Output Junior Herkomst\n{state.get('herkomst_middelen', '[GEEN OUTPUT]')}\n\n"
        f"## Output Junior Vermogen\n{state.get('hnwi_status', '[GEEN OUTPUT]')}\n\n"
    )

    if state.get("senior_feedback"):
        user_content += (
            "## Eerdere feedback\n"
            + "\n".join(f"- {fb}" for fb in state["senior_feedback"])
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
    approved = "GOEDGEKEURD" in content.upper() or iteration >= max_iterations

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
