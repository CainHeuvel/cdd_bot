"""Report Agent — final Markdown formatter (light model)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_light_llm
from prompts.system_prompts import REPORT_PROMPT_PARTICULIER, REPORT_PROMPT_ZAKELIJK


def _strip_code_blocks(text: str) -> str:
    """Remove any code blocks that may have leaked into the report text."""
    return re.sub(r"```[\s\S]*?```", "", text).strip()


def _extract_senior_classification(senior_review: str, risicoclassificatie: str) -> str:
    """Extract only the risk classification and rationale from senior review.

    Strips internal feedback, validation notes and status markers.
    """
    parts = []
    if risicoclassificatie:
        parts.append(f"Risicoclassificatie: {risicoclassificatie}")

    # Try to extract the rationale paragraph from the senior review
    match = re.search(
        r"(?:\*\*)?(?:Onderbouwing|Toelichting)\s*(?:classificatie)?(?:\*\*)?[:\s]*(.+?)(?=\n\n|\n\*\*|$)",
        senior_review,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        parts.append(match.group(1).strip())
    elif risicoclassificatie and senior_review:
        # Fallback: look for text after the classification mention
        match2 = re.search(
            rf"{re.escape(risicoclassificatie)}[:\s.]*(.+?)(?=\n\n|\n\*\*|$)",
            senior_review,
            re.IGNORECASE | re.DOTALL,
        )
        if match2:
            parts.append(match2.group(1).strip())

    return "\n".join(parts) if parts else risicoclassificatie


def report_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Format approved outputs into the final CDD Markdown report.

    Reads: client_type, klantprofiel, herkomst_middelen, hnwi_status,
           verklaard_vermogen, risicoclassificatie, senior_review
    Writes: final_report, current_agent
    """
    client_type: str = state["client_type"]
    is_zakelijk = client_type.lower() == "zakelijk"

    system_prompt = REPORT_PROMPT_ZAKELIJK if is_zakelijk else REPORT_PROMPT_PARTICULIER

    # Extract only the classification + rationale, not feedback/validation notes
    senior_review = state.get("senior_review", "")
    risicoclassificatie = state.get("risicoclassificatie", "[GEEN CLASSIFICATIE]")
    classificatie_tekst = _extract_senior_classification(senior_review, risicoclassificatie)

    user_content = (
        f"## Toelichting analist\n{state.get('toelichting', '')}\n\n"
        f"## Goedgekeurde output van de Junior Agents\n\n"
        f"### Klantprofiel / Structuur\n{state.get('klantprofiel', '[GEEN OUTPUT]')}\n\n"
        f"### Herkomst van middelen\n{state.get('herkomst_middelen', '[GEEN OUTPUT]')}\n\n"
        f"### HNWI Status en vermogen\n{state.get('hnwi_status', '[GEEN OUTPUT]')}\n\n"
        f"### Verklaard vermogen komend jaar\n{state.get('verklaard_vermogen', '[GEEN OUTPUT]')}\n\n"
        f"### Risicoclassificatie en onderbouwing\n{classificatie_tekst}\n\n"
    )

    llm = get_light_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ])

    # Strip any code blocks that may have leaked into the report text
    clean_report = _strip_code_blocks(response.content)

    return {
        "final_report": clean_report,
        "current_agent": "report",
    }
