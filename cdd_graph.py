"""LangGraph state machine for the CDD multi-agent pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from agents.manager import manager_agent
from agents.juniors import (
    junior_herkomst_agent,
    junior_structuur_agent,
    junior_vermogen_agent,
)
from agents.recon import recon_agent
from agents.report import report_agent
from agents.senior import senior_agent
from config import get_settings


# ─── State definition ─────────────────────────────────────────────────────────

class CddState(TypedDict, total=False):
    client_type: str
    toelichting: str
    documents: list[dict[str, Any]]

    recon_index: str
    manager_instructions: str

    # Gestructureerde secties (Pydantic .model_dump() dicts)
    identificatie_sectie: dict | None
    klantprofiel_sectie: dict | None
    screening_sectie: dict | None
    structuur_ubo_sectie: dict | None
    herkomst_sectie: dict | None
    transactieprofiel_sectie: dict | None

    # Organogram (zakelijk)
    organogram_svg: str
    organogram_data: dict | None
    organogram_warning: str

    analyst_feedback: list[str]
    senior_feedback: list[str]
    senior_approved: bool
    senior_review: str
    risicoclassificatie: str
    iteration_count: int

    final_report: str
    current_agent: str


# ─── Conditional edge: Manager → parallel Juniors via Send() ──────────────────

def _fan_out_to_juniors(state: CddState) -> list[Send]:
    """Dispatch work to all three Junior agents in parallel."""
    return [
        Send("junior_structuur", state),
        Send("junior_herkomst", state),
        Send("junior_vermogen", state),
    ]


# ─── Conditional edge: Senior → Report or back to Manager ────────────────────

def _after_senior(state: CddState) -> str:
    """Route based on senior approval or iteration cap."""
    if state.get("senior_approved", False):
        return "report"
    max_iter = get_settings().max_senior_iterations
    if state.get("iteration_count", 0) >= max_iter:
        return "report"
    return "manager"


# ─── Graph construction ──────────────────────────────────────────────────────

def build_graph() -> CompiledStateGraph:
    """Build and compile the CDD LangGraph state machine."""
    graph = StateGraph(CddState)

    # Nodes
    graph.add_node("recon", recon_agent)
    graph.add_node("manager", manager_agent)
    graph.add_node("junior_structuur", junior_structuur_agent)
    graph.add_node("junior_herkomst", junior_herkomst_agent)
    graph.add_node("junior_vermogen", junior_vermogen_agent)
    graph.add_node("senior", senior_agent)
    graph.add_node("report", report_agent)

    # Edges: START → Recon → Manager
    graph.set_entry_point("recon")
    graph.add_edge("recon", "manager")

    # Manager → parallel Juniors (fan-out via Send)
    graph.add_conditional_edges("manager", _fan_out_to_juniors)

    # Juniors → Senior (fan-in)
    graph.add_edge("junior_structuur", "senior")
    graph.add_edge("junior_herkomst", "senior")
    graph.add_edge("junior_vermogen", "senior")

    # Senior → Report or back to Manager (feedback loop)
    graph.add_conditional_edges(
        "senior",
        _after_senior,
        {"report": "report", "manager": "manager"},
    )

    # Report → END
    graph.add_edge("report", END)

    return graph.compile()
