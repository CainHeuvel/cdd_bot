"""Pydantic models for structured organogram data."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class NodeType(str, Enum):
    """Entity type in the ownership structure."""

    PERSON = "person"
    BV = "bv"
    NV = "nv"
    STICHTING = "stichting"
    VOF = "vof"
    OTHER = "other"


class OrganogramNode(BaseModel):
    """A single entity (company or natural person) in the organogram."""

    id: str = Field(
        ...,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
        description="Unique alphanumeric identifier, e.g. 'UBO1', 'HoldingBV'",
    )
    label: str = Field(
        ...,
        max_length=80,
        description="Display label, e.g. 'J. Jansen (UBO)' or 'Holding BV'",
    )
    node_type: NodeType = Field(
        ...,
        description="Type of entity: person, bv, nv, stichting, vof, other",
    )


class OrganogramEdge(BaseModel):
    """An ownership relationship between two entities."""

    source: str = Field(..., description="Node ID of the parent/owner")
    target: str = Field(..., description="Node ID of the child/subsidiary")
    percentage: str | None = Field(
        None,
        description="Ownership percentage, e.g. '100%' or '60%'",
    )


class OrganogramData(BaseModel):
    """Complete organogram: nodes (entities) and edges (ownership relations)."""

    nodes: list[OrganogramNode] = Field(
        ...,
        min_length=1,
        description="All entities in the ownership structure",
    )
    edges: list[OrganogramEdge] = Field(
        default_factory=list,
        description="Ownership relationships between entities",
    )

    @model_validator(mode="after")
    def validate_edge_references(self) -> OrganogramData:
        """Ensure all edge source/target IDs reference existing nodes."""
        node_ids = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(
                    f"Edge source '{edge.source}' does not match any node ID"
                )
            if edge.target not in node_ids:
                raise ValueError(
                    f"Edge target '{edge.target}' does not match any node ID"
                )
        return self
