"""Report Agent — final Markdown formatter (light model)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_light_llm
from prompts.system_prompts import REPORT_PROMPT_PARTICULIER, REPORT_PROMPT_ZAKELIJK


def _strip_code_blocks(text: str) -> str:
    """Remove any code blocks that may have leaked into the report text."""
    return re.sub(r"```[\s\S]*?```", "", text).strip()


def _format_sectie(label: str, sectie: dict | None) -> str:
    """Format a Pydantic dict section as readable JSON for LLM consumption."""
    if sectie is None:
        return f"### {label}\n[GEEN OUTPUT]\n"
    return f"### {label}\n```json\n{json.dumps(sectie, indent=2, ensure_ascii=False)}\n```\n"


def report_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Format approved outputs into the final CDD Markdown report.

    Reads: all structured dict sections, organogram_svg,
           risicoclassificatie, senior_onderbouwing_classificatie
    Writes: final_report, current_agent
    """
    client_type: str = state["client_type"]
    is_zakelijk = client_type.lower() == "zakelijk"

    system_prompt = REPORT_PROMPT_ZAKELIJK if is_zakelijk else REPORT_PROMPT_PARTICULIER

    risicoclassificatie = state.get("risicoclassificatie", "[GEEN CLASSIFICATIE]")
    senior_rationale = state.get(
        "senior_onderbouwing_classificatie",
        state.get("senior_review", ""),
    )

    secties = (
        _format_sectie("Identificatie & Verificatie", state.get("identificatie_sectie"))
        + _format_sectie("Klantprofiel", state.get("klantprofiel_sectie"))
        + _format_sectie("Screening", state.get("screening_sectie"))
        + _format_sectie("Structuur & UBO", state.get("structuur_ubo_sectie"))
        + _format_sectie("Herkomst van Middelen", state.get("herkomst_sectie"))
        + _format_sectie("Transactieprofiel", state.get("transactieprofiel_sectie"))
    )

    user_content = (
        f"## Toelichting analist\n{state.get('toelichting', '')}\n\n"
        f"## Goedgekeurde output van de Junior Agents\n\n{secties}\n"
        f"### Risicoclassificatie (Senior Agent)\nRisicoclassificatie: {risicoclassificatie}\n\n"
        f"### Onderbouwing classificatie (Senior Agent)\n{senior_rationale}\n\n"
    )

    organogram_svg = state.get("organogram_svg", "")
    if is_zakelijk and organogram_svg:
        user_content += (
            "### Organogram\n"
            "Het organogram is beschikbaar als SVG en wordt apart weergegeven in de applicatie. "
            "Neem het NIET op in het rapport.\n\n"
        )

    llm = get_light_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ])

    clean_report = _strip_code_blocks(response.content)

    return {
        "final_report": clean_report,
        "current_agent": "report",
    }
