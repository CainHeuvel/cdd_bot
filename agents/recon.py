"""Recon Agent — document-indexeerder (heavy model)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_heavy_llm
from prompts.system_prompts import RECON_PROMPT

MAX_RAW_TEXT_CHARS = 12000
MAX_TABLE_CHARS = 4000


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Return truncated text and whether truncation happened."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def recon_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Read raw OCR output and produce a structured document index.

    Reads: documents
    Writes: recon_index, current_agent
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
    response = llm.invoke([
        SystemMessage(content=RECON_PROMPT),
        HumanMessage(content=user_content),
    ])

    return {
        "recon_index": response.content,
        "current_agent": "recon",
    }
