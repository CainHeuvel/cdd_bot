"""Junior Agents — three task-specific specialists (light model).

- Junior Structuur: client profile / ownership structure + organogram
- Junior Herkomst: source-of-funds assessment per Bijlage 1
- Junior Vermogen: HNWI status + declared wealth next year
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_light_llm
from models.organogram import OrganogramData
from prompts.system_prompts import (
    JUNIOR_HERKOMST_PROMPT,
    JUNIOR_STRUCTUUR_PROMPT,
    JUNIOR_VERMOGEN_PROMPT,
    ORGANOGRAM_EXTRACTION_PROMPT,
)
from rendering.organogram import render_organogram_svg

logger = logging.getLogger(__name__)


def _build_user_message(state: dict[str, Any]) -> str:
    """Build the shared context block that every Junior receives."""
    client_type: str = state["client_type"]
    toelichting: str = state["toelichting"]
    recon_index: str = state["recon_index"]
    manager_instructions: str = state.get("manager_instructions", "")
    senior_feedback: list[str] = state.get("senior_feedback", [])

    parts = [
        f"## Client type\n{client_type}",
        f"## Toelichting analist\n{toelichting}",
        f"## Document-index (Recon Agent)\n{recon_index}",
    ]
    if manager_instructions:
        parts.append(f"## Instructies van de Manager Agent\n{manager_instructions}")
    if senior_feedback:
        parts.append(
            "## Feedback Senior Agent (vorige iteratie)\n"
            + "\n".join(f"- {fb}" for fb in senior_feedback)
        )
    return "\n\n".join(parts)


def junior_structuur_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Build client profile (particulier) or ownership structure (zakelijk).

    Writes: klantprofiel, organogram_svg, organogram_data
    """
    llm = get_light_llm()

    # Step 1: textual analysis (klantprofiel / structuurbeschrijving)
    response = llm.invoke([
        SystemMessage(content=JUNIOR_STRUCTUUR_PROMPT),
        HumanMessage(content=_build_user_message(state)),
    ])
    content: str = response.content

    # Step 2: for business clients, extract structured organogram
    organogram_svg = ""
    organogram_data = None

    if state.get("client_type", "").lower() == "zakelijk":
        try:
            structured_llm = llm.with_structured_output(OrganogramData)
            result = structured_llm.invoke([
                SystemMessage(content=ORGANOGRAM_EXTRACTION_PROMPT),
                HumanMessage(content=content),
            ])
            organogram_svg = render_organogram_svg(result)
            organogram_data = result.model_dump()
        except Exception:
            logger.warning("Organogram extraction failed", exc_info=True)

    return {
        "klantprofiel": content,
        "organogram_svg": organogram_svg,
        "organogram_data": organogram_data,
    }


def junior_herkomst_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Assess source of funds per Bijlage 1.

    Writes: herkomst_middelen
    """
    llm = get_light_llm()
    response = llm.invoke([
        SystemMessage(content=JUNIOR_HERKOMST_PROMPT),
        HumanMessage(content=_build_user_message(state)),
    ])

    return {
        "herkomst_middelen": response.content,
    }


def junior_vermogen_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Determine HNWI status and declared wealth for next year.

    Writes: hnwi_status, verklaard_vermogen
    """
    llm = get_light_llm()
    response = llm.invoke([
        SystemMessage(content=JUNIOR_VERMOGEN_PROMPT),
        HumanMessage(content=_build_user_message(state)),
    ])

    content: str = response.content

    # Split output into HNWI and wealth sections based on prompt headings
    verklaard_split = re.split(
        r"###?\s*Verklaard vermogen komend jaar", content, maxsplit=1, flags=re.IGNORECASE
    )
    hnwi_section = verklaard_split[0].strip()
    verklaard_section = verklaard_split[1].strip() if len(verklaard_split) > 1 else content

    return {
        "hnwi_status": hnwi_section,
        "verklaard_vermogen": verklaard_section,
    }
