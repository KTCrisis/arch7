"""Shared test fixtures for arch7 tests."""

from __future__ import annotations

import pytest

from arch7_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    Node,
    ShapeType,
    Subgraph,
)


@pytest.fixture
def simple_graph() -> DiagramGraph:
    """A minimal 3-node linear graph: A -> B -> C."""
    return DiagramGraph(
        nodes=[
            Node(id="a", label="Service A"),
            Node(id="b", label="Service B"),
            Node(id="c", label="Service C"),
        ],
        edges=[
            Edge(from_id="a", to_id="b"),
            Edge(from_id="b", to_id="c"),
        ],
        direction=Direction.LEFT_RIGHT,
    )


@pytest.fixture
def typed_graph() -> DiagramGraph:
    """A graph with typed components (DB, cache, queue)."""
    return DiagramGraph(
        nodes=[
            Node(id="api", label="API Gateway", component_type="nginx"),
            Node(id="svc", label="Backend"),
            Node(id="db", label="PostgreSQL", component_type="postgresql"),
            Node(id="cache", label="Redis", component_type="redis"),
            Node(id="queue", label="Kafka", component_type="kafka"),
        ],
        edges=[
            Edge(from_id="api", to_id="svc"),
            Edge(from_id="svc", to_id="db"),
            Edge(from_id="svc", to_id="cache", style=EdgeStyle.DASHED),
            Edge(from_id="svc", to_id="queue", style=EdgeStyle.DASHED),
        ],
        direction=Direction.LEFT_RIGHT,
    )


@pytest.fixture
def nested_subgraph_graph() -> DiagramGraph:
    """A graph with nested subgraphs: outer > inner."""
    return DiagramGraph(
        nodes=[
            Node(id="fe", label="Frontend"),
            Node(id="be", label="Backend"),
            Node(id="db", label="Cloud SQL", component_type="cloud sql"),
        ],
        edges=[
            Edge(from_id="fe", to_id="be"),
            Edge(from_id="be", to_id="db"),
        ],
        subgraphs=[
            Subgraph(
                id="k8s",
                label="GKE Cluster",
                node_ids=["fe", "be"],
                component_type="kubernetes",
            ),
            Subgraph(
                id="gcp",
                label="Google Cloud",
                node_ids=["db"],
                child_ids=["k8s"],
                component_type="googlecloud",
            ),
        ],
        direction=Direction.LEFT_RIGHT,
    )
