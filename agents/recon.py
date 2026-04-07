"""Recon Agent — document-indexeerder (heavy model)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm
from models.agent_contracts import ReconEvidenceIndex
from observability import invoke_structured
from prompts.system_prompts import RECON_PROMPT

MAX_RAW_TEXT_CHARS = 12000
MAX_TABLE_CHARS = 4000


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Return truncated text and whether truncation happened."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _render_recon_index(evidence: ReconEvidenceIndex) -> str:
    """Render structured Recon evidence back into readable Markdown."""
    sections: list[str] = []
    for idx, doc in enumerate(evidence.documents, start=1):
        lines = [
            f"### Document {idx}: {doc.readable_name}",
            f"- Type document: {doc.document_type}",
        ]
        if doc.entities:
            lines.append("- Entiteiten: " + "; ".join(doc.entities))
        if doc.amounts:
            lines.append("- Bedragen: " + "; ".join(doc.amounts))
        if doc.dates:
            lines.append("- Datums: " + "; ".join(doc.dates))
        if doc.bijlage1_sources:
            lines.append("- Bijlage 1 classificatie: " + "; ".join(doc.bijlage1_sources))
        if doc.key_facts:
            lines.append("- Kernfeiten: " + "; ".join(doc.key_facts))
        if doc.table_summary:
            lines.append(f"- Tabellen: {doc.table_summary}")
        if doc.opmerkingen:
            lines.append(f"- Opmerkingen: {doc.opmerkingen}")
        sections.append("\n".join(lines))

    if evidence.global_observations:
        sections.append(
            "### Algemene observaties\n"
            + "\n".join(f"- {item}" for item in evidence.global_observations)
        )

    return "\n\n".join(sections)


def recon_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Read raw OCR output and produce a structured document index.

    Reads: documents, toelichting
    Writes: recon_index, recon_evidence, current_agent
    """
    documents: list[dict[str, Any]] = state["documents"]
    toelichting: str = state.get("toelichting", "")

    doc_summaries: list[str] = []
    for i, doc in enumerate(documents, 1):
        raw_text = str(doc.get("raw_text", ""))
        tables = str(doc.get("tables", ""))
        raw_text_short, raw_truncated = _truncate(raw_text, MAX_RAW_TEXT_CHARS)
        tables_short, tables_truncated = _truncate(tables, MAX_TABLE_CHARS)
        trunc_note = ""
        if raw_truncated or tables_truncated:
            trunc_note = (
                "\n[LET OP] Ingekort voor performance: "
                f"raw_text={len(raw_text_short)}/{len(raw_text)} chars, "
                f"tables={len(tables_short)}/{len(tables)} chars.\n"
            )
        doc_summaries.append(
            f"--- Document {i}: {doc['filename']} ---\n"
            f"TEKST:\n{raw_text_short}\n\n"
            f"TABELLEN:\n{tables_short}\n"
            f"{trunc_note}"
        )

    user_content = (
        "## Toelichting analist\n"
        f"{toelichting}\n\n"
        "## OCR-resultaten\n"
        "Hieronder staan de OCR-resultaten van de aangeleverde documenten. "
        "Maak een gestructureerde index conform je instructies.\n\n"
        + "\n\n".join(doc_summaries)
    )

    llm = get_heavy_llm()
    evidence = invoke_structured("recon", llm, ReconEvidenceIndex, [
        SystemMessage(content=RECON_PROMPT),
        HumanMessage(content=user_content),
    ])

    return {
        "recon_index": _render_recon_index(evidence),
        "recon_evidence": json.loads(evidence.model_dump_json()),
        "current_agent": "recon",
    }
