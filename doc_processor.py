"""Azure Document Intelligence wrapper for PDF extraction."""

from __future__ import annotations

import logging
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError

from config import get_settings

logger = logging.getLogger(__name__)


def _table_to_markdown(table: Any) -> str:
    """Convert a Document Intelligence table to a Markdown table string."""
    if not table.cells:
        return ""

    max_row = max(c.row_index for c in table.cells) + 1
    max_col = max(c.column_index for c in table.cells) + 1
    grid: list[list[str]] = [[""] * max_col for _ in range(max_row)]

    for cell in table.cells:
        grid[cell.row_index][cell.column_index] = (cell.content or "").replace("\n", " ").strip()

    lines: list[str] = []
    for i, row in enumerate(grid):
        lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def process_documents(files: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """Process uploaded PDF files via Azure Document Intelligence.

    Args:
        files: List of (filename, file_bytes) tuples.

    Returns:
        List of dicts with keys: filename, raw_text, tables (as Markdown).
    """
    settings = get_settings()
    client = DocumentIntelligenceClient(
        endpoint=settings.azure_doc_intel_endpoint,
        credential=AzureKeyCredential(settings.azure_doc_intel_key),
    )

    results: list[dict[str, Any]] = []

    for filename, file_bytes in files:
        try:
            poller = client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(bytes_source=file_bytes),
            )
            result = poller.result()

            raw_text = result.content or ""

            tables_md: list[str] = []
            if result.tables:
                for idx, table in enumerate(result.tables):
                    tables_md.append(f"### Tabel {idx + 1}\n{_table_to_markdown(table)}")

            results.append({
                "filename": filename,
                "raw_text": raw_text,
                "tables": "\n\n".join(tables_md),
            })
            logger.info("Verwerkt: %s (%d karakters, %d tabellen)", filename, len(raw_text), len(tables_md))

        except (HttpResponseError, ServiceRequestError) as exc:
            logger.exception("Azure API fout bij verwerken van %s: %s", filename, type(exc).__name__)
            results.append({
                "filename": filename,
                "raw_text": f"[FOUT: Kon {filename} niet verwerken — {type(exc).__name__}]",
                "tables": "",
            })
        except Exception:
            logger.exception("Onverwachte fout bij verwerken van %s", filename)
            results.append({
                "filename": filename,
                "raw_text": f"[FOUT: Kon {filename} niet verwerken]",
                "tables": "",
            })

    return results
