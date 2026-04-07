"""Tests for the Sugiyama layout engine."""

from __future__ import annotations

import pytest

from arch7_mcp.core.models import (
    DiagramGraph,
    Direction,
    Edge,
    Node,
    ShapeType,
    Subgraph,
)
from arch7_mcp.engine.layout import compute_layout


# ---------------------------------------------------------------------------
# Basic layout
# ---------------------------------------------------------------------------


class TestBasicLayout:
    def test_empty_graph(self):
        layout = compute_layout(DiagramGraph())
        assert len(layout.nodes) == 0
        assert len(layout.edges) == 0

    def test_single_node(self):
        graph = DiagramGraph(nodes=[Node(id="a", label="A")])
        layout = compute_layout(graph)
        assert len(layout.nodes) == 1
        pn = layout.nodes[0]
        assert pn.width > 0
        assert pn.height > 0

    def test_linear_chain(self, simple_graph):
        layout = compute_layout(simple_graph)
        assert len(layout.nodes) == 3
        assert len(layout.edges) == 2

    def test_all_nodes_have_positive_dimensions(self, typed_graph):
        layout = compute_layout(typed_graph)
        for pn in layout.nodes:
            assert pn.width > 0, f"Node {pn.node.id} has zero width"
            assert pn.height > 0, f"Node {pn.node.id} has zero height"


# ---------------------------------------------------------------------------
# Non-overlapping
# ---------------------------------------------------------------------------


class TestNoOverlap:
    def _rects_overlap(self, a, b) -> bool:
        """Check if two positioned nodes overlap (with small tolerance)."""
        tol = 2.0
        return not (
            a.x + a.width <= b.x + tol
            or b.x + b.width <= a.x + tol
            or a.y + a.height <= b.y + tol
            or b.y + b.height <= a.y + tol
        )

    def test_no_overlapping_nodes(self, typed_graph):
        layout = compute_layout(typed_graph)
        nodes = layout.nodes
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                assert not self._rects_overlap(nodes[i], nodes[j]), (
                    f"Nodes {nodes[i].node.id} and {nodes[j].node.id} overlap"
                )

    def test_no_overlap_large_graph(self):
        """10-node graph should not have overlaps."""
        nodes = [Node(id=f"n{i}", label=f"Service {i}") for i in range(10)]
        edges = [Edge(from_id=f"n{i}", to_id=f"n{i+1}") for i in range(9)]
        graph = DiagramGraph(nodes=nodes, edges=edges, direction=Direction.LEFT_RIGHT)
        layout = compute_layout(graph)

        pns = layout.nodes
        for i in range(len(pns)):
            for j in range(i + 1, len(pns)):
                assert not self._rects_overlap(pns[i], pns[j])


# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------


class TestDirectionLayout:
    def test_lr_nodes_progress_rightward(self):
        graph = DiagramGraph(
            nodes=[Node(id="a", label="A"), Node(id="b", label="B")],
            edges=[Edge(from_id="a", to_id="b")],
            direction=Direction.LEFT_RIGHT,
        )
        layout = compute_layout(graph)
        node_map = {pn.node.id: pn for pn in layout.nodes}
        assert node_map["a"].x < node_map["b"].x

    def test_td_nodes_progress_downward(self):
        graph = DiagramGraph(
            nodes=[Node(id="a", label="A"), Node(id="b", label="B")],
            edges=[Edge(from_id="a", to_id="b")],
            direction=Direction.TOP_DOWN,
        )
        layout = compute_layout(graph)
        node_map = {pn.node.id: pn for pn in layout.nodes}
        assert node_map["a"].y < node_map["b"].y


# ---------------------------------------------------------------------------
# Node sizing
# ---------------------------------------------------------------------------


class TestNodeSizing:
    def test_cylinder_v_shape_preserves_size(self):
        graph = DiagramGraph(
            nodes=[Node(id="db", label="PostgreSQL", component_type="postgresql")],
        )
        layout = compute_layout(graph)
        pn = layout.nodes[0]
        assert pn.width >= 100
        assert pn.height >= 40

    def test_diamond_shape_smaller_than_rect(self):
        graph = DiagramGraph(
            nodes=[
                Node(id="rect", label="Same Label"),
                Node(id="dia", label="Same Label", shape=ShapeType.DIAMOND),
            ],
        )
        layout = compute_layout(graph)
        node_map = {pn.node.id: pn for pn in layout.nodes}
        assert node_map["dia"].width <= node_map["rect"].width

    def test_icon_widens_node(self):
        """Nodes with icons should be wider than those without."""
        graph = DiagramGraph(
            nodes=[
                Node(id="plain", label="A Reasonably Long Service Name"),
                Node(id="typed", label="A Reasonably Long Service Name", component_type="redis"),
            ],
        )
        layout = compute_layout(graph)
        node_map = {pn.node.id: pn for pn in layout.nodes}
        assert node_map["typed"].width > node_map["plain"].width


# ---------------------------------------------------------------------------
# Subgraphs preserved
# ---------------------------------------------------------------------------


class TestSubgraphsPreserved:
    def test_subgraphs_passed_through(self, nested_subgraph_graph):
        layout = compute_layout(nested_subgraph_graph)
        assert len(layout.subgraphs) == 2
        sg_ids = {sg.id for sg in layout.subgraphs}
        assert "k8s" in sg_ids
        assert "gcp" in sg_ids


# ---------------------------------------------------------------------------
# Edge routing
# ---------------------------------------------------------------------------


class TestEdgeRouting:
    def test_edges_have_points(self, simple_graph):
        layout = compute_layout(simple_graph)
        for pe in layout.edges:
            assert len(pe.points) >= 2, f"Edge {pe.edge.from_id}->{pe.edge.to_id} has no points"

    def test_disconnected_components(self):
        """Two disconnected pairs should both be laid out."""
        graph = DiagramGraph(
            nodes=[
                Node(id="a", label="A"),
                Node(id="b", label="B"),
                Node(id="c", label="C"),
                Node(id="d", label="D"),
            ],
            edges=[
                Edge(from_id="a", to_id="b"),
                Edge(from_id="c", to_id="d"),
            ],
        )
        layout = compute_layout(graph)
        assert len(layout.nodes) == 4
        assert len(layout.edges) == 2
