"""Streamlit UI for the CDD Rapportage Tool."""

from __future__ import annotations

import base64
import json
import queue
import threading
import time
import logging
from typing import Any

import streamlit as st

from cdd_graph import CddState, build_graph
from doc_processor import process_documents
from observability import TokenUsageHandler

logger = logging.getLogger("cdd_pipeline")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CDD Rapportage",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session state defaults ──────────────────────────────────────────────────

for key, default in [
    ("phase", "input"),              # "input" | "review"
    ("final_state", {}),             # Geaccumuleerde state na graph run
    ("run_count", 0),                # Iteratie-teller voor re-runs
    ("approved", False),             # Rapport goedgekeurd?
    ("analyst_feedback", []),        # Geaccumuleerde analist-feedback
    ("processed_documents", None),   # Gecachte doc_processor output
    ("cached_client_type", None),    # Gecacht klanttype bij eerste run
    ("cached_toelichting", None),    # Gecachte toelichting bij eerste run
]:
    st.session_state.setdefault(key, default)

# ─── Agent display metadata ──────────────────────────────────────────────────

AGENT_LABELS: dict[str, str] = {
    "recon": "Recon: documenten indexeren…",
    "manager": "Manager: workflow en instructies…",
    "junior_structuur": "Junior Structuur: klantprofiel / eigendomsstructuur…",
    "junior_herkomst": "Junior Herkomst: herkomst middelen (Bijlage 1)…",
    "junior_vermogen": "Junior Vermogen: transactieprofiel…",
    "senior": "Senior: validatie tegen Wwft-beleid…",
    "report": "Report: opmaak eindrapport…",
}

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 30
MAX_FILE_COUNT = 20

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _collect_categorized_files(
    files_id: list | None,
    files_struct: list | None,
    files_herkomst: list | None,
    files_overig: list | None,
) -> list[tuple[str, bytes]]:
    """Merge categorized uploads into a single list with category prefix."""
    mapping = [
        ("Identificatie", files_id or []),
        ("Structuur", files_struct or []),
        ("Herkomst", files_herkomst or []),
        ("Overig", files_overig or []),
    ]
    result: list[tuple[str, bytes]] = []
    for category, files in mapping:
        for f in files:
            result.append((f"[{category}] {f.name}", f.getvalue()))
    return result


def _run_graph(
    input_state: CddState,
    update_queue: queue.Queue[dict[str, Any] | None],
) -> None:
    """Run the compiled LangGraph in a background thread.

    Streams node-level updates into *update_queue*.  Sends ``None`` as a
    sentinel value when the graph finishes.
    """
    token_handler = TokenUsageHandler()

    logger.info(
        "Pipeline start | client_type=%s | documents=%d",
        input_state.get("client_type"),
        len(input_state.get("documents", [])),
    )
    try:
        compiled = build_graph()
        for idx, chunk in enumerate(
            compiled.stream(
                input_state,
                stream_mode="updates",
                config={"callbacks": [token_handler]},
            ),
            start=1,
        ):
            logger.info("Graph update #%d | nodes=%s", idx, list(chunk.keys()))
            update_queue.put(chunk)
    except Exception as exc:
        logger.exception("Pipeline exception: %s", exc)
        update_queue.put({"__error__": str(exc)})
    finally:
        summary = token_handler.summary()
        logger.info(
            "Pipeline finished | %s",
            " | ".join(f"{k}={v}" for k, v in summary.items()),
        )
        update_queue.put(None)


def _build_raw_data_json(final_state: dict[str, Any]) -> str:
    """Build a JSON export of all structured CDD sections."""
    keys = [
        "identificatie_sectie",
        "klantprofiel_sectie",
        "screening_sectie",
        "structuur_ubo_sectie",
        "herkomst_sectie",
        "transactieprofiel_sectie",
        "risicoclassificatie",
        "senior_review",
        "organogram_data",
    ]
    raw = {k: final_state.get(k) for k in keys if final_state.get(k) is not None}
    return json.dumps(raw, indent=2, ensure_ascii=False)


def _build_svg_data_uri(svg: str) -> str:
    """Encode trusted SVG markup as an image data URI for display."""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("CDD Rapportage")
    st.caption("Customer Due Diligence — ondersteuning voor analisten")
    st.divider()

    client_type = st.radio(
        "Klanttype",
        options=["Particulier", "Zakelijk"],
        horizontal=True,
        help="Bepaalt welke Bijlage 1 (particulier of zakelijk) en het rapporttemplate worden toegepast.",
    )

    toelichting = st.text_area(
        "Toelichting",
        height=200,
        label_visibility="visible",
        placeholder=(
            "Beschrijf de klant, de relatie en relevante context. "
            "Vermeld bekende bronnen van middelen, werkgever of structuur waar van toepassing."
        ),
    )

    # ── Gecategoriseerde uploads ──
    st.subheader("Bewijsstukken (PDF)")

    files_identificatie = st.file_uploader(
        "1. Identificatie & Verificatie",
        type=["pdf"],
        accept_multiple_files=True,
        key="upload_identificatie",
        help="Paspoort, ID-bewijs, iDIN-rapport, etc.",
    )

    files_structuur: list = []
    if client_type == "Zakelijk":
        files_structuur = st.file_uploader(
            "2. Bedrijfsstructuur",
            type=["pdf"],
            accept_multiple_files=True,
            key="upload_structuur",
            help="KvK-uittreksel, aandeelhoudersregister, statuten, etc.",
        )

    files_herkomst = st.file_uploader(
        "3. Herkomst van Middelen",
        type=["pdf"],
        accept_multiple_files=True,
        key="upload_herkomst",
        help="Loonstroken, jaarrekening, bankafschriften, nota van afrekening, etc.",
    )

    files_overig = st.file_uploader(
        "4. Overige documenten",
        type=["pdf"],
        accept_multiple_files=True,
        key="upload_overig",
        help="Overige relevante documenten.",
    )

    generate = st.button("Rapport genereren", type="primary", use_container_width=True)


# ─── Main area: Pipeline execution ──────────────────────────────────────────

def _run_pipeline() -> None:
    """Execute the CDD pipeline (initial run or re-run after feedback)."""
    is_rerun = st.session_state.processed_documents is not None

    # ── Collect & validate uploads (only on first run) ──
    if not is_rerun:
        all_uploaded = _collect_categorized_files(
            files_identificatie, files_structuur, files_herkomst, files_overig,
        )
        if not toelichting.strip():
            st.error("Voer een toelichting in voordat je het rapport genereert.")
            st.stop()
        if not all_uploaded:
            st.error("Upload minimaal één PDF-bewijsstuk.")
            st.stop()
        if len(all_uploaded) > MAX_FILE_COUNT:
            st.error(f"Maximaal {MAX_FILE_COUNT} bestanden toegestaan.")
            st.stop()

        for name, file_bytes in all_uploaded:
            if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"Bestand '{name}' is groter dan {MAX_FILE_SIZE_MB} MB.")
                st.stop()
            if not file_bytes[:5].startswith(b"%PDF"):
                st.error(f"Bestand '{name}' is geen geldig PDF-bestand.")
                st.stop()

        # Process documents via Azure Document Intelligence
        doc_start = time.monotonic()
        logger.info("Document processing start | files=%d", len(all_uploaded))
        with st.status("Documentverwerking (Azure Document Intelligence)", expanded=True) as doc_status:
            st.write(f"Bezig met {len(all_uploaded)} bestand(en)…")
            documents = process_documents(all_uploaded)
            st.session_state.processed_documents = documents
            st.session_state.cached_client_type = client_type.lower()
            st.session_state.cached_toelichting = toelichting
            doc_status.update(
                label=f"Documentverwerking voltooid ({len(documents)} bestand(en))",
                state="complete",
            )
        logger.info(
            "Document processing complete | files=%d | elapsed=%.1fs",
            len(documents), time.monotonic() - doc_start,
        )
    else:
        documents = st.session_state.processed_documents

    # ── Build input state ──
    input_state: CddState = {
        "client_type": st.session_state.cached_client_type,
        "toelichting": st.session_state.cached_toelichting,
        "documents": documents,
    }
    if st.session_state.analyst_feedback:
        input_state["analyst_feedback"] = list(st.session_state.analyst_feedback)

    # ── Run LangGraph pipeline ──
    st.session_state.run_count += 1
    update_q: queue.Queue[dict[str, Any] | None] = queue.Queue()
    thread = threading.Thread(target=_run_graph, args=(input_state, update_q))

    run_label = "Analyse — multi-agent pipeline"
    if st.session_state.run_count > 1:
        run_label += f" (iteratie {st.session_state.run_count}, na feedback)"
    status_container = st.status(run_label, expanded=True)
    seen_agents: set[str] = set()
    final_state: dict[str, Any] = {}
    status_container.write("Recon gestart — grote documentsets kunnen langer duren.")
    last_progress_ts = time.monotonic()
    heartbeat_seconds = 15

    thread.start()

    while True:
        try:
            update = update_q.get(timeout=1.0)
        except queue.Empty:
            now = time.monotonic()
            if now - last_progress_ts >= heartbeat_seconds:
                status_container.write(
                    "Nog bezig met analyse… wacht op volgende stap (mogelijk grote input of retries)."
                )
                last_progress_ts = now
            continue

        if update is None:
            break

        if "__error__" in update:
            status_container.update(label="Fout in pipeline", state="error")
            st.error(f"Pipelinefout: {update['__error__']}")
            st.stop()

        for node_name, state_updates in update.items():
            if isinstance(state_updates, dict):
                final_state.update(state_updates)

                agent_key = state_updates.get("current_agent", node_name)
                label = AGENT_LABELS.get(agent_key, f"Stap: {agent_key}…")

                iteration = state_updates.get("iteration_count")
                is_feedback_round = iteration is not None and iteration > 1

                if is_feedback_round and agent_key == "senior":
                    status_container.write(
                        f"⟲ Senior: feedback teruggestuurd (iteratie {iteration})"
                    )
                elif agent_key not in seen_agents or is_feedback_round:
                    seen_agents.add(agent_key)
                    if is_feedback_round:
                        status_container.write(f"⟲ {label} (iteratie {iteration})")
                    else:
                        status_container.write(label)
                last_progress_ts = time.monotonic()

    thread.join(timeout=300)
    status_container.update(label="Pipeline voltooid", state="complete")

    # ── Transition to review phase ──
    st.session_state.final_state = final_state
    st.session_state.phase = "review"
    st.session_state.approved = False
    st.rerun()


# ─── Main area: Review interface ─────────────────────────────────────────────

def _show_review() -> None:
    """Display the generated report and approve/reject controls."""
    final_state = st.session_state.final_state
    final_report: str = final_state.get("final_report", "")
    organogram_svg: str = final_state.get("organogram_svg", "")
    organogram_warning: str = final_state.get("organogram_warning", "")
    is_zakelijk = st.session_state.cached_client_type == "zakelijk"

    if not final_report:
        st.warning("Geen rapport gegenereerd. Controleer de logs.")
        st.stop()

    # ── Status badges ──
    if st.session_state.run_count > 1:
        st.info(f"Rapport iteratie {st.session_state.run_count} (na feedback van analist)")

    if "ONTBREKEND" in final_report.upper():
        st.warning(
            "Het rapport bevat nog ontbrekende informatie. "
            "Controleer de secties gemarkeerd met **ONTBREKEND** en vraag de benodigde documenten op."
        )

    # ── Rapport ──
    st.markdown(final_report)

    # ── Organogram (zakelijk) ──
    if is_zakelijk and organogram_svg:
        st.divider()
        st.subheader("Eigendomsstructuur")
        organogram_src = _build_svg_data_uri(organogram_svg)
        st.html(
            f'<div style="width:100%;overflow-x:auto;">'
            f'<img src="{organogram_src}" alt="Organogram" style="max-width:100%;height:auto;" />'
            "</div>"
        )
    elif is_zakelijk and organogram_warning:
        st.warning(organogram_warning)

    st.divider()

    # ── Approve / Reject ──
    if not st.session_state.approved:
        col_approve, col_reject = st.columns(2)

        with col_approve:
            st.subheader("Rapport Goedkeuren")
            if st.button("✅ Rapport Goedkeuren", type="primary", use_container_width=True):
                st.session_state.approved = True
                st.rerun()

        with col_reject:
            st.subheader("Afkeuren & Aanpassen")
            feedback_text = st.text_area(
                "Feedback voor heranalyse",
                placeholder="Beschrijf wat er moet worden aangepast of aangevuld…",
                height=150,
                key=f"feedback_input_{st.session_state.run_count}",
            )
            if st.button("❌ Feedback verzenden & opnieuw analyseren", use_container_width=True):
                if not feedback_text.strip():
                    st.error("Voer feedback in voordat je opnieuw analyseert.")
                else:
                    st.session_state.analyst_feedback.append(feedback_text.strip())
                    st.session_state.phase = "input"
                    st.rerun()
    else:
        # ── Post-approval: downloads ──
        st.success("Rapport is goedgekeurd!")

        col_dl_report, col_dl_data = st.columns(2)

        with col_dl_report:
            st.download_button(
                label="📄 Download rapport (.md)",
                data=final_report,
                file_name="cdd_rapport.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with col_dl_data:
            st.download_button(
                label="📊 Download ruwe data (.json)",
                data=_build_raw_data_json(final_state),
                file_name="cdd_raw_data.json",
                mime="application/json",
                use_container_width=True,
            )


# ─── Main area: Welcome page ─────────────────────────────────────────────────

def _show_welcome() -> None:
    """Display the welcome/landing page."""
    st.header("CDD Rapportage")
    st.markdown(
        "Ondersteuning bij het opstellen van Customer Due Diligence-rapportage "
        "in lijn met het interne Wwft-beleid. Gebruik de zijbalk om invoer te starten."
    )
    st.subheader("Werkwijze")
    st.markdown(
        """
        1. Selecteer **klanttype** (particulier of zakelijk).
        2. Vul de **toelichting** in met relevante context.
        3. **Upload PDF-bewijsstukken** in de juiste categorie: Identificatie, Bedrijfsstructuur (zakelijk), Herkomst van Middelen, of Overige documenten.
        4. Kies **Rapport genereren** en volg de status van de analyse.
        """
    )
    st.subheader("Pipeline")
    st.markdown(
        """
        - **Recon** — documenten structureren (geen inhoudelijke conclusies).
        - **Manager** — taken verdelen op basis van klanttype en documenten.
        - **Junior Structuur** — klantprofiel, identificatie, screening en eigendomsstructuur (incl. organogram waar van toepassing).
        - **Junior Herkomst** — herkomst van middelen tegen Bijlage 1.
        - **Junior Vermogen** — transactieprofiel: verwachte stortingen, opnames en verklaard vermogen.
        - **Senior** — validatie tegen beleid; bij gebreken wordt feedback teruggegeven aan de eerdere stappen.
        - **Report** — opmaak van het eindrapport in Markdown.
        """
    )


# ─── Routing ──────────────────────────────────────────────────────────────────

if generate or (st.session_state.phase == "input" and st.session_state.analyst_feedback):
    _run_pipeline()
elif st.session_state.phase == "review":
    _show_review()
else:
    _show_welcome()
