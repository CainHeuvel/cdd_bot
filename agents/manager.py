"""Manager Agent — workflow-manager (heavy model)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm
from prompts.system_prompts import MANAGER_PROMPT


def manager_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Assess input and produce instructions for each Junior agent.

    Reads: client_type, toelichting, recon_index, analyst_feedback, senior_feedback
    Writes: manager_instructions, current_agent
    """
    client_type: str = state["client_type"]
    toelichting: str = state["toelichting"]
    recon_index: str = state["recon_index"]
    analyst_feedback: list[str] = state.get("analyst_feedback", [])
    senior_feedback: list[str] = state.get("senior_feedback", [])

    feedback_block = ""
    if analyst_feedback:
        feedback_block += (
            "\n\n## Feedback van de analist\n"
            + "\n".join(f"- {fb}" for fb in analyst_feedback)
        )
    if senior_feedback:
        feedback_block = (
            f"{feedback_block}\n\n## Feedback van de Senior Agent uit vorige iteratie\n"
            + "\n".join(f"- {fb}" for fb in senior_feedback)
            + "\n\nVerwerk deze feedback in je instructies aan de Juniors."
        )

    user_content = (
        f"## Client type\n{client_type}\n\n"
        f"## Toelichting analist\n{toelichting}\n\n"
        f"## Document-index (Recon Agent)\n{recon_index}"
        f"{feedback_block}"
    )

    llm = get_heavy_llm()
    response = llm.invoke([
        SystemMessage(content=MANAGER_PROMPT),
        HumanMessage(content=user_content),
    ])

    return {
        "manager_instructions": response.content,
        "current_agent": "manager",
    }
