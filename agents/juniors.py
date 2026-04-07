"""Junior Agents — three task-specific specialists (light model).

- Junior Structuur: client profile / ownership structure + organogram
- Junior Herkomst: source-of-funds assessment per Bijlage 1
- Junior Vermogen: HNWI status + declared wealth next year
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_light_llm
from models.agent_contracts import JuniorStructuurParticulier, JuniorStructuurZakelijk
from models.cdd_dossier import (
    HerkomstMiddelen,
    Transactieprofiel,
)
from models.organogram import OrganogramData
from prompts.system_prompts import (
    JUNIOR_HERKOMST_PROMPT,
    JUNIOR_STRUCTUUR_PROMPT,
    JUNIOR_VERMOGEN_PROMPT,
    ORGANOGRAM_EXTRACTION_PROMPT,
)
from rendering.organogram import render_organogram_svg

logger = logging.getLogger(__name__)


def _build_user_message(
    state: dict[str, Any],
    *,
    instruction_key: str | None = None,
) -> str:
    """Build the context block for a Junior agent.

    Args:
        state: The full CddState dict.
        instruction_key: If provided, use this state key for the Manager
            instruction (e.g. ``"manager_instructie_herkomst"``).
    """
    client_type: str = state["client_type"]
    toelichting: str = state["toelichting"]
    recon_index: str = state["recon_index"]

    manager_instructions = state.get(instruction_key, "") if instruction_key else state.get("manager_instructions", "")
    manager_feedback_algemeen: str = state.get("manager_feedback_algemeen", "")
    analyst_feedback: list[str] = state.get("analyst_feedback", [])

    parts = [
        f"## Client type\n{client_type}",
        f"## Toelichting analist\n{toelichting}",
        f"## Document-index (Recon Agent)\n{recon_index}",
    ]
    if manager_feedback_algemeen:
        parts.append(f"## Algemene instructie van de Manager Agent\n{manager_feedback_algemeen}")
    if manager_instructions:
        parts.append(f"## Instructies van de Manager Agent\n{manager_instructions}")
    if analyst_feedback:
        parts.append(
            "## Feedback analist\n"
            + "\n".join(f"- {fb}" for fb in analyst_feedback)
        )
    return "\n\n".join(parts)


def junior_structuur_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Build client profile, identification, screening and (zakelijk) ownership structure.

    Uses a single combined LLM call per client type to avoid drift between
    sections and reduce token waste from repeated context.

    Writes: identificatie_sectie, klantprofiel_sectie, screening_sectie,
            structuur_ubo_sectie, organogram_svg, organogram_data, organogram_warning
    """
    llm = get_light_llm()
    messages = [
        SystemMessage(content=JUNIOR_STRUCTUUR_PROMPT),
        HumanMessage(content=_build_user_message(state, instruction_key="manager_instructie_structuur")),
    ]
    is_zakelijk = state.get("client_type", "").lower() == "zakelijk"

    structuur_ubo_sectie = None
    organogram_svg = ""
    organogram_data = None
    organogram_warning = ""

    if is_zakelijk:
        combined = llm.with_structured_output(JuniorStructuurZakelijk).invoke(messages)
        structuur_ubo_sectie = combined.structuur_en_ubo.model_dump()

        try:
            organogram_llm = llm.with_structured_output(OrganogramData)
            eigendomsstructuur_tekst = combined.structuur_en_ubo.eigendomsstructuur.antwoord
            if combined.structuur_en_ubo.eigendomsstructuur.toelichting:
                eigendomsstructuur_tekst += "\n" + combined.structuur_en_ubo.eigendomsstructuur.toelichting
            org_result = organogram_llm.invoke([
                SystemMessage(content=ORGANOGRAM_EXTRACTION_PROMPT),
                HumanMessage(content=eigendomsstructuur_tekst),
            ])
            organogram_svg = render_organogram_svg(org_result)
            organogram_data = org_result.model_dump()
        except Exception:
            logger.warning("Organogram extraction failed", exc_info=True)
            organogram_warning = (
                "Het organogram kon niet automatisch worden opgebouwd. "
                "Controleer of Graphviz lokaal is geinstalleerd en of de eigendomsstructuur "
                "voldoende duidelijk is beschreven."
            )
    else:
        combined = llm.with_structured_output(JuniorStructuurParticulier).invoke(messages)

    return {
        "identificatie_sectie": combined.identificatie_verificatie.model_dump(),
        "klantprofiel_sectie": combined.klantprofiel.model_dump(),
        "screening_sectie": combined.screening.model_dump(),
        "structuur_ubo_sectie": structuur_ubo_sectie,
        "organogram_svg": organogram_svg,
        "organogram_data": organogram_data,
        "organogram_warning": organogram_warning,
    }


def junior_herkomst_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Assess source of funds per Bijlage 1.

    Writes: herkomst_sectie
    """
    llm = get_light_llm()
    structured_llm = llm.with_structured_output(HerkomstMiddelen)
    messages = [
        SystemMessage(content=JUNIOR_HERKOMST_PROMPT),
        HumanMessage(content=_build_user_message(state, instruction_key="manager_instructie_herkomst")),
    ]
    result: HerkomstMiddelen = structured_llm.invoke(messages)

    return {
        "herkomst_sectie": result.model_dump(),
    }


def junior_vermogen_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Extract transaction profile: expected deposits, withdrawals, declared wealth.

    Writes: transactieprofiel_sectie
    """
    llm = get_light_llm()
    structured_llm = llm.with_structured_output(Transactieprofiel)
    messages = [
        SystemMessage(content=JUNIOR_VERMOGEN_PROMPT),
        HumanMessage(content=_build_user_message(state, instruction_key="manager_instructie_vermogen")),
    ]
    result: Transactieprofiel = structured_llm.invoke(messages)

    return {
        "transactieprofiel_sectie": result.model_dump(),
    }
