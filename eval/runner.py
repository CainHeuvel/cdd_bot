"""Evaluation runner: load gold dossiers, execute the pipeline, score results.

Usage (from project root)::

    python -m eval.runner                       # run all gold dossiers
    python -m eval.runner --dossier particulier_laag_risico.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from cdd_graph import build_graph
from doc_processor import process_documents
from observability import TokenUsageHandler

from eval.scorer import ScoreResult, score_run

logger = logging.getLogger("cdd_pipeline.eval")

GOLD_DIR = Path(__file__).parent / "gold_dossiers"


def _load_dossier(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_pdfs(pdf_paths: list[str], base_dir: Path) -> list[tuple[str, bytes]]:
    """Read PDF files from disk and return as (filename, bytes) tuples."""
    files: list[tuple[str, bytes]] = []
    for rel_path in pdf_paths:
        full_path = base_dir / rel_path
        if not full_path.exists():
            logger.warning("PDF not found, skipping: %s", full_path)
            continue
        files.append((full_path.name, full_path.read_bytes()))
    return files


def run_single(dossier_path: Path) -> ScoreResult:
    """Execute the full pipeline for one gold dossier and return scored results."""
    dossier = _load_dossier(dossier_path)
    name = dossier.get("name", dossier_path.stem)
    logger.info("=== Running gold dossier: %s ===", name)

    pdf_files = _load_pdfs(
        dossier.get("pdf_paths", []),
        dossier_path.parent,
    )

    if not pdf_files:
        logger.error("No PDFs found for dossier %s — skipping", name)
        result = ScoreResult(name=name, passed=False)
        result.details.append("No PDF files found")
        return result

    documents = process_documents(pdf_files)

    input_state = {
        "client_type": dossier["client_type"],
        "toelichting": dossier["toelichting"],
        "documents": documents,
    }

    token_handler = TokenUsageHandler()
    compiled = build_graph()

    final_state: dict[str, Any] = {}
    for chunk in compiled.stream(
        input_state,
        stream_mode="updates",
        config={"callbacks": [token_handler]},
    ):
        for node_name, node_output in chunk.items():
            if isinstance(node_output, dict):
                final_state.update(node_output)

    result = score_run(
        final_state=final_state,
        expected=dossier.get("expected", {}),
        name=name,
        token_summary=token_handler.summary(),
    )

    logger.info(result.summary_line())
    for detail in result.details:
        logger.info("  - %s", detail)

    return result


def run_all() -> list[ScoreResult]:
    """Run all gold dossiers in the gold_dossiers directory."""
    results: list[ScoreResult] = []
    dossier_files = sorted(
        p for p in GOLD_DIR.glob("*.json")
        if not p.name.startswith("_")
    )

    if not dossier_files:
        logger.warning("No gold dossiers found in %s", GOLD_DIR)
        return results

    for dossier_path in dossier_files:
        try:
            result = run_single(dossier_path)
            results.append(result)
        except Exception:
            logger.exception("Failed to run dossier: %s", dossier_path.name)
            failed = ScoreResult(name=dossier_path.stem, passed=False)
            failed.details.append("Unhandled exception during run")
            results.append(failed)

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    for r in results:
        print(r.summary_line())
    print(f"\n{passed}/{len(results)} dossiers passed")
    print("=" * 70)

    return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run CDD evaluation suite")
    parser.add_argument(
        "--dossier",
        type=str,
        default=None,
        help="Run a single gold dossier by filename (e.g. 'particulier_laag.json')",
    )
    args = parser.parse_args()

    if args.dossier:
        path = GOLD_DIR / args.dossier
        if not path.exists():
            print(f"Dossier not found: {path}", file=sys.stderr)
            sys.exit(1)
        result = run_single(path)
        sys.exit(0 if result.passed else 1)
    else:
        results = run_all()
        sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
