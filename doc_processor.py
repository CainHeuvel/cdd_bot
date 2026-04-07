"""Azure Document Intelligence wrapper for PDF extraction."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError

from config import get_settings

logger = logging.getLogger(__name__)

_MAX_WORKERS = 5


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


def _process_single(
    client: DocumentIntelligenceClient,
    filename: str,
    file_bytes: bytes,
) -> dict[str, Any]:
    """Process a single PDF file via Azure Document Intelligence."""
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

        logger.info("Verwerkt: %s (%d karakters, %d tabellen)", filename, len(raw_text), len(tables_md))
        return {
            "filename": filename,
            "raw_text": raw_text,
            "tables": "\n\n".join(tables_md),
        }

    except (HttpResponseError, ServiceRequestError) as exc:
        logger.exception("Azure API fout bij verwerken van %s: %s", filename, type(exc).__name__)
        return {
            "filename": filename,
            "raw_text": f"[FOUT: Kon {filename} niet verwerken — {type(exc).__name__}]",
            "tables": "",
        }
    except Exception:
        logger.exception("Onverwachte fout bij verwerken van %s", filename)
        return {
            "filename": filename,
            "raw_text": f"[FOUT: Kon {filename} niet verwerken]",
            "tables": "",
        }


def process_documents(files: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """Process uploaded PDF files via Azure Document Intelligence.

    Files are processed in parallel (up to ``_MAX_WORKERS`` concurrent calls)
    to reduce wall-clock time. Results are returned in the original order.

    Args:
        files: List of (filename, file_bytes) tuples.

    Returns:
        List of dicts with keys: filename, raw_text, tables (as Markdown).
    """
    if not files:
        return []

    settings = get_settings()
    client = DocumentIntelligenceClient(
        endpoint=settings.azure_doc_intel_endpoint,
        credential=AzureKeyCredential(settings.azure_doc_intel_key),
    )

    results: list[dict[str, Any] | None] = [None] * len(files)

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(files))) as pool:
        future_to_idx = {
            pool.submit(_process_single, client, filename, file_bytes): idx
            for idx, (filename, file_bytes) in enumerate(files)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    return results  # type: ignore[return-value]
