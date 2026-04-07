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
from models.cdd_dossier import (
    HerkomstMiddelen,
    IdentificatieVerificatie,
    IdentificatieVerificatieZakelijk,
    KlantprofielParticulier,
    KlantprofielZakelijk,
    Screening,
    ScreeningZakelijk,
    StructuurEnUbo,
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


def _build_user_message(state: dict[str, Any]) -> str:
    """Build the shared context block that every Junior receives."""
    client_type: str = state["client_type"]
    toelichting: str = state["toelichting"]
    recon_index: str = state["recon_index"]
    manager_instructions: str = state.get("manager_instructions", "")
    analyst_feedback: list[str] = state.get("analyst_feedback", [])
    senior_feedback: list[str] = state.get("senior_feedback", [])

    parts = [
        f"## Client type\n{client_type}",
        f"## Toelichting analist\n{toelichting}",
        f"## Document-index (Recon Agent)\n{recon_index}",
    ]
    if manager_instructions:
        parts.append(f"## Instructies van de Manager Agent\n{manager_instructions}")
    if analyst_feedback:
        parts.append(
            "## Feedback analist\n"
            + "\n".join(f"- {fb}" for fb in analyst_feedback)
        )
    if senior_feedback:
        parts.append(
            "## Feedback Senior Agent (vorige iteratie)\n"
            + "\n".join(f"- {fb}" for fb in senior_feedback)
        )
    return "\n\n".join(parts)


def junior_structuur_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Build client profile, identification, screening and (zakelijk) ownership structure.

    Writes: identificatie_sectie, klantprofiel_sectie, screening_sectie,
            structuur_ubo_sectie, organogram_svg, organogram_data
    """
    llm = get_light_llm()
    messages = [
        SystemMessage(content=JUNIOR_STRUCTUUR_PROMPT),
        HumanMessage(content=_build_user_message(state)),
    ]
    is_zakelijk = state.get("client_type", "").lower() == "zakelijk"

    # --- Identificatie & verificatie ---
    if is_zakelijk:
        id_model = IdentificatieVerificatieZakelijk
    else:
        id_model = IdentificatieVerificatie

    identificatie = llm.with_structured_output(id_model).invoke(messages)

    # --- Klantprofiel ---
    if is_zakelijk:
        profiel_model = KlantprofielZakelijk
    else:
        profiel_model = KlantprofielParticulier

    klantprofiel = llm.with_structured_output(profiel_model).invoke(messages)

    # --- Screening ---
    if is_zakelijk:
        screening_model = ScreeningZakelijk
    else:
        screening_model = Screening

    screening = llm.with_structured_output(screening_model).invoke(messages)

    # --- Structuur & UBO + Organogram (alleen zakelijk) ---
    structuur_ubo_sectie = None
    organogram_svg = ""
    organogram_data = None
    organogram_warning = ""

    if is_zakelijk:
        structuur_ubo = llm.with_structured_output(StructuurEnUbo).invoke(messages)
        structuur_ubo_sectie = structuur_ubo.model_dump()

        # Organogram extraction vanuit de eigendomsstructuur-beschrijving
        try:
            organogram_llm = llm.with_structured_output(OrganogramData)
            eigendomsstructuur_tekst = structuur_ubo.eigendomsstructuur.antwoord
            if structuur_ubo.eigendomsstructuur.toelichting:
                eigendomsstructuur_tekst += "\n" + structuur_ubo.eigendomsstructuur.toelichting
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

    return {
        "identificatie_sectie": identificatie.model_dump(),
        "klantprofiel_sectie": klantprofiel.model_dump(),
        "screening_sectie": screening.model_dump(),
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
        HumanMessage(content=_build_user_message(state)),
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
        HumanMessage(content=_build_user_message(state)),
    ]
    result: Transactieprofiel = structured_llm.invoke(messages)

    return {
        "transactieprofiel_sectie": result.model_dump(),
    }
