"""Streamlit UI for the CDD Rapportage Tool."""

from __future__ import annotations

import queue
import re
import threading
import time
import logging
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from cdd_graph import CddState, build_graph
from doc_processor import process_documents

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

# ─── Agent display metadata (plain text for status log) ────────────────────────

AGENT_LABELS: dict[str, str] = {
    "recon": "Recon: documenten indexeren…",
    "manager": "Manager: workflow en instructies…",
    "junior_structuur": "Junior Structuur: klantprofiel / eigendomsstructuur…",
    "junior_herkomst": "Junior Herkomst: herkomst middelen (Bijlage 1)…",
    "junior_vermogen": "Junior Vermogen: HNWI en verklaard vermogen…",
    "senior": "Senior: validatie tegen Wwft-beleid…",
    "report": "Report: opmaak eindrapport…",
}

# ─── Background graph runner ─────────────────────────────────────────────────


def _run_graph(
    input_state: CddState,
    update_queue: queue.Queue[dict[str, Any] | None],
) -> None:
    """Run the compiled LangGraph in a background thread.

    Streams node-level updates into *update_queue*.  Sends ``None`` as a
    sentinel value when the graph finishes.
    """
    logger.info(
        "Pipeline start | client_type=%s | documents=%d",
        input_state.get("client_type"),
        len(input_state.get("documents", [])),
    )
    try:
        compiled = build_graph()
        for idx, chunk in enumerate(compiled.stream(input_state, stream_mode="updates"), start=1):
            logger.info("Graph update #%d | nodes=%s", idx, list(chunk.keys()))
            update_queue.put(chunk)
    except Exception as exc:
        logger.exception("Pipeline exception: %s", exc)
        update_queue.put({"__error__": str(exc)})
    finally:
        logger.info("Pipeline finished (sentinel queued)")
        update_queue.put(None)


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

    uploaded_files = st.file_uploader(
        "Bewijsstukken (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Eén of meer PDF’s; tekst en tabellen worden via Document Intelligence uitgelezen.",
    )

    generate = st.button("Rapport genereren", type="primary", use_container_width=True)

# ─── Main area ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 30
MAX_FILE_COUNT = 20

if generate:
    # Validate inputs
    if not toelichting.strip():
        st.error("Voer een toelichting in voordat je het rapport genereert.")
        st.stop()
    if not uploaded_files:
        st.error("Upload minimaal één PDF-bewijsstuk.")
        st.stop()
    if len(uploaded_files) > MAX_FILE_COUNT:
        st.error(f"Maximaal {MAX_FILE_COUNT} bestanden toegestaan.")
        st.stop()

    # Validate each uploaded file
    for f in uploaded_files:
        file_bytes = f.getvalue()
        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"Bestand '{f.name}' is groter dan {MAX_FILE_SIZE_MB} MB.")
            st.stop()
        if not file_bytes[:5].startswith(b"%PDF"):
            st.error(f"Bestand '{f.name}' is geen geldig PDF-bestand.")
            st.stop()

    # ── Step 1: Process documents via Azure Document Intelligence ──
    doc_process_started_at = time.monotonic()
    logger.info("Document processing start | files=%d", len(uploaded_files))
    with st.status("Documentverwerking (Azure Document Intelligence)", expanded=True) as doc_status:
        file_tuples: list[tuple[str, bytes]] = [
            (f.name, f.getvalue()) for f in uploaded_files
        ]
        st.write(f"Bezig met {len(file_tuples)} bestand(en)…")
        documents = process_documents(file_tuples)
        doc_status.update(label=f"Documentverwerking voltooid ({len(documents)} bestand(en))", state="complete")
    logger.info(
        "Document processing complete | files=%d | elapsed=%.1fs",
        len(documents),
        time.monotonic() - doc_process_started_at,
    )

    # ── Step 2: Run the LangGraph pipeline ──
    input_state: CddState = {
        "client_type": client_type.lower(),
        "toelichting": toelichting,
        "documents": documents,
    }

    update_q: queue.Queue[dict[str, Any] | None] = queue.Queue()
    thread = threading.Thread(target=_run_graph, args=(input_state, update_q))

    status_container = st.status("Analyse — multi-agent pipeline", expanded=True)
    seen_agents: set[str] = set()
    final_state: dict[str, Any] = {}
    status_container.write("Recon gestart — grote documentsets kunnen langer duren.")
    last_progress_msg_ts = time.monotonic()
    heartbeat_seconds = 15

    thread.start()

    while True:
        try:
            update = update_q.get(timeout=1.0)
        except queue.Empty:
            now = time.monotonic()

            if now - last_progress_msg_ts >= heartbeat_seconds:
                status_container.write(
                    "Nog bezig met analyse… wacht op volgende stap (mogelijk grote input of retries)."
                )
                last_progress_msg_ts = now
            continue

        if update is None:
            break

        if "__error__" in update:
            status_container.update(label="Fout in pipeline", state="error")
            st.error(f"Pipelinefout: {update['__error__']}")
            st.stop()

        # update is a dict like {"node_name": {state_updates}}
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
                last_progress_msg_ts = time.monotonic()

    thread.join(timeout=300)
    status_container.update(label="Pipeline voltooid", state="complete")

    # ── Step 3: Display results ──
    final_report = final_state.get("final_report", "")
    organogram_svg = final_state.get("organogram_svg", "")

    if not final_report:
        st.warning("Geen rapport gegenereerd. Controleer de logs.")
        st.stop()

    # Warnings for missing info
    if "ONTBREKEND" in final_report.upper():
        st.warning(
            "Het rapport bevat nog ontbrekende informatie. "
            "Controleer de secties gemarkeerd met **ONTBREKEND** en vraag de benodigde documenten op."
        )

    # Tabs
    if organogram_svg and client_type.lower() == "zakelijk":
        tab_rapport, tab_organogram = st.tabs(["Rapport", "Organogram"])
    else:
        tab_rapport = st.tabs(["Rapport"])[0]
        tab_organogram = None

    with tab_rapport:
        # ── Parse rapport into sections and display each in its own text area ──
        _sections = re.split(r"^(#{1,2}\s+.+)$", final_report, flags=re.MULTILINE)

        # _sections alternates: [preamble, heading1, body1, heading2, body2, ...]
        report_sections: list[tuple[str, str]] = []
        preamble = _sections[0].strip() if _sections else ""
        if preamble:
            report_sections.append(("Rapport", preamble))
        for i in range(1, len(_sections) - 1, 2):
            heading = _sections[i].strip().lstrip("#").strip()
            # Remove leading number + dot (e.g. "1. Aanleiding" -> "Aanleiding")
            heading = re.sub(r"^\d+\.\s*", "", heading)
            body = _sections[i + 1].strip() if i + 1 < len(_sections) else ""
            if heading and body:
                report_sections.append((heading, body))

        for idx, (section_title, section_body) in enumerate(report_sections):
            st.markdown(f"**{section_title}**")
            st.text_area(
                section_title,
                value=section_body,
                height=max(100, min(400, section_body.count("\n") * 24 + 80)),
                key=f"section_{idx}",
                label_visibility="collapsed",
            )

        # ── Copy full report button ──
        st.divider()
        components.html(
            f"""
            <button onclick="copyReport()" style="
                background-color: #ff4b4b; color: white; border: none;
                padding: 0.5rem 1rem; border-radius: 0.3rem; cursor: pointer;
                font-size: 0.9rem; font-weight: 500;
            ">Volledig rapport kopiëren</button>
            <span id="copy-feedback" style="margin-left: 1rem; color: #28a745; display: none;">Gekopieerd!</span>
            <script>
            function copyReport() {{
                const text = {repr(final_report)};
                navigator.clipboard.writeText(text).then(function() {{
                    var fb = document.getElementById('copy-feedback');
                    fb.style.display = 'inline';
                    setTimeout(function() {{ fb.style.display = 'none'; }}, 2000);
                }});
            }}
            </script>
            """,
            height=50,
        )

    if tab_organogram is not None:
        with tab_organogram:
            st.subheader("Eigendomsstructuur")
            st.html(
                f'<div style="width:100%;overflow-x:auto;">{organogram_svg}</div>'
            )

elif not generate:
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
        3. **Upload PDF-bewijsstukken** (bijvoorbeeld loonstroken, jaarrekening, KvK-uittreksel).
        4. Kies **Rapport genereren** en volg de status van de analyse.
        """
    )
    st.subheader("Pipeline")
    st.markdown(
        """
        - **Recon** — documenten structureren (geen inhoudelijke conclusies).
        - **Manager** — taken verdelen op basis van klanttype en documenten.
        - **Junior Structuur** — klantprofiel of eigendomsstructuur (incl. organogram waar van toepassing).
        - **Junior Herkomst** — herkomst van middelen tegen Bijlage 1.
        - **Junior Vermogen** — HNWI-indicatie en verklaard vermogen.
        - **Senior** — validatie tegen beleid; bij gebreken wordt feedback teruggegeven aan de eerdere stappen.
        - **Report** — opmaak van het eindrapport in Markdown.
        """
    )
