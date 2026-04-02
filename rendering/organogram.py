"""Render an OrganogramData model to SVG using Graphviz."""

from __future__ import annotations

import graphviz

from models.organogram import NodeType, OrganogramData

# Visual style per node type
_NODE_STYLES: dict[NodeType, dict[str, str]] = {
    NodeType.PERSON: {
        "shape": "ellipse",
        "style": "filled",
        "fillcolor": "#E8F4FD",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
    NodeType.BV: {
        "shape": "box",
        "style": "filled,rounded",
        "fillcolor": "#FFF3E0",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
    NodeType.NV: {
        "shape": "box",
        "style": "filled,rounded",
        "fillcolor": "#FFF3E0",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
    NodeType.STICHTING: {
        "shape": "box",
        "style": "filled",
        "fillcolor": "#F3E5F5",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
    NodeType.VOF: {
        "shape": "box",
        "style": "filled,rounded",
        "fillcolor": "#E8F5E9",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
    NodeType.OTHER: {
        "shape": "box",
        "style": "filled",
        "fillcolor": "#F5F5F5",
        "fontname": "Helvetica",
        "fontsize": "11",
    },
}


def render_organogram_svg(data: OrganogramData) -> str:
    """Convert validated organogram data to an SVG string."""
    dot = graphviz.Digraph(
        format="svg",
        engine="dot",
        graph_attr={
            "rankdir": "TB",
            "splines": "ortho",
            "nodesep": "0.8",
            "ranksep": "1.0",
            "bgcolor": "transparent",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "10",
            "color": "#666666",
        },
    )

    for node in data.nodes:
        style = _NODE_STYLES.get(node.node_type, _NODE_STYLES[NodeType.OTHER])
        dot.node(node.id, label=node.label, **style)

    for edge in data.edges:
        label = edge.percentage if edge.percentage else ""
        dot.edge(edge.source, edge.target, label=label)

    return dot.pipe(encoding="utf-8")
