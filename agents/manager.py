"""Manager Agent — workflow-manager (heavy model)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm
from models.agent_contracts import ManagerInstructions
from prompts.system_prompts import MANAGER_PROMPT


def manager_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Assess input and produce per-junior instructions.

    Reads: client_type, toelichting, recon_index, analyst_feedback, senior_feedback,
           senior_feedback_structuur, senior_feedback_herkomst, senior_feedback_vermogen
    Writes: manager_instructions, manager_feedback_algemeen, manager_instructie_structuur,
            manager_instructie_herkomst, manager_instructie_vermogen, current_agent
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
        feedback_block += (
            "\n\n## Feedback van de Senior Agent uit vorige iteratie\n"
            + "\n".join(f"- {fb}" for fb in senior_feedback)
            + "\n\nVerwerk deze feedback in je instructies aan de Juniors."
        )

    # Include per-junior feedback from Senior for targeted instructions
    per_junior_block = ""
    for label, key in [
        ("Junior Structuur", "senior_feedback_structuur"),
        ("Junior Herkomst", "senior_feedback_herkomst"),
        ("Junior Vermogen", "senior_feedback_vermogen"),
    ]:
        fb = state.get(key, "")
        if fb:
            per_junior_block += f"\n### Senior feedback specifiek voor {label}\n{fb}\n"

    if per_junior_block:
        feedback_block += f"\n\n## Per-junior feedback van de Senior Agent{per_junior_block}"

    user_content = (
        f"## Client type\n{client_type}\n\n"
        f"## Toelichting analist\n{toelichting}\n\n"
        f"## Document-index (Recon Agent)\n{recon_index}"
        f"{feedback_block}"
    )

    llm = get_heavy_llm()
    structured_llm = llm.with_structured_output(ManagerInstructions)
    instructions: ManagerInstructions = structured_llm.invoke([
        SystemMessage(content=MANAGER_PROMPT),
        HumanMessage(content=user_content),
    ])

    return {
        "manager_instructions": "\n\n".join(
            part
            for part in [
                (
                    f"**Algemeen**: {instructions.feedback_algemeen}"
                    if instructions.feedback_algemeen
                    else ""
                ),
                f"**Structuur**: {instructions.instructie_structuur}",
                f"**Herkomst**: {instructions.instructie_herkomst}",
                f"**Vermogen**: {instructions.instructie_vermogen}",
            ]
            if part
        ),
        "manager_feedback_algemeen": instructions.feedback_algemeen or "",
        "manager_instructie_structuur": instructions.instructie_structuur,
        "manager_instructie_herkomst": instructions.instructie_herkomst,
        "manager_instructie_vermogen": instructions.instructie_vermogen,
        "current_agent": "manager",
    }
