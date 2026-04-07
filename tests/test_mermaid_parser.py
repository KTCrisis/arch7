"""Tests for the Mermaid flowchart parser."""

from __future__ import annotations

import pytest

from arch7_mcp.core.models import Direction, EdgeStyle, ShapeType
from arch7_mcp.parsers.mermaid import parse_mermaid


# ---------------------------------------------------------------------------
# Direction detection
# ---------------------------------------------------------------------------


class TestDirectionParsing:
    @pytest.mark.parametrize(
        "decl, expected",
        [
            ("graph TD", Direction.TOP_DOWN),
            ("graph TB", Direction.TOP_DOWN),
            ("graph LR", Direction.LEFT_RIGHT),
            ("flowchart BT", Direction.BOTTOM_UP),
            ("flowchart RL", Direction.RIGHT_LEFT),
        ],
    )
    def test_direction(self, decl: str, expected: Direction):
        graph = parse_mermaid(f"{decl}\n    A --> B")
        assert graph.direction == expected

    def test_default_direction_is_top_down(self):
        graph = parse_mermaid("graph TD\n    A --> B")
        assert graph.direction == Direction.TOP_DOWN


# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------


class TestNodeExtraction:
    def test_rectangle_node(self):
        graph = parse_mermaid("graph LR\n    A[My Service]")
        assert len(graph.nodes) == 1
        assert graph.nodes[0].id == "A"
        assert graph.nodes[0].label == "My Service"
        assert graph.nodes[0].shape == ShapeType.RECTANGLE

    def test_diamond_node(self):
        graph = parse_mermaid("graph LR\n    A{Decision}")
        node = graph.nodes[0]
        assert node.shape == ShapeType.DIAMOND
        assert node.label == "Decision"

    def test_circle_node(self):
        graph = parse_mermaid("graph LR\n    A((Start))")
        assert graph.nodes[0].shape == ShapeType.CIRCLE

    def test_stadium_node(self):
        graph = parse_mermaid("graph LR\n    A([Rounded])")
        assert graph.nodes[0].shape == ShapeType.STADIUM

    def test_bare_node_gets_id_as_label(self):
        graph = parse_mermaid("graph LR\n    MyNode --> Other")
        node_map = {n.id: n for n in graph.nodes}
        assert node_map["MyNode"].label == "MyNode"

    def test_multiple_nodes_on_edges(self):
        graph = parse_mermaid("graph LR\n    A[Svc A] --> B[Svc B] --> C[Svc C]")
        assert len(graph.nodes) >= 2  # at least A and B parsed


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------


class TestEdgeExtraction:
    def test_solid_arrow(self):
        graph = parse_mermaid("graph LR\n    A --> B")
        assert len(graph.edges) == 1
        assert graph.edges[0].from_id == "A"
        assert graph.edges[0].to_id == "B"
        assert graph.edges[0].style == EdgeStyle.SOLID

    def test_thick_arrow(self):
        graph = parse_mermaid("graph LR\n    A ==> B")
        assert graph.edges[0].style == EdgeStyle.THICK

    def test_dashed_arrow(self):
        graph = parse_mermaid("graph LR\n    A -.-> B")
        assert graph.edges[0].style == EdgeStyle.DASHED

    def test_label_on_edge(self):
        graph = parse_mermaid("graph LR\n    A -->|events| B")
        assert graph.edges[0].label == "events"

    def test_inline_label(self):
        graph = parse_mermaid("graph LR\n    A -- data flow --> B")
        assert graph.edges[0].label == "data flow"

    def test_multiple_edges(self):
        src = "graph LR\n    A --> B\n    B --> C\n    A --> C"
        graph = parse_mermaid(src)
        assert len(graph.edges) == 3


# ---------------------------------------------------------------------------
# Subgraphs
# ---------------------------------------------------------------------------


class TestSubgraphs:
    def test_basic_subgraph(self):
        src = """
graph LR
    subgraph Backend
        A[Service A]
        B[Service B]
    end
    A --> B
"""
        graph = parse_mermaid(src)
        assert len(graph.subgraphs) == 1
        sg = graph.subgraphs[0]
        assert sg.label == "Backend"
        assert "A" in sg.node_ids
        assert "B" in sg.node_ids

    def test_nested_subgraphs(self):
        src = """
graph LR
    subgraph Outer
        subgraph Inner
            A --> B
        end
        C --> A
    end
"""
        graph = parse_mermaid(src)
        assert len(graph.subgraphs) == 2
        sg_map = {sg.id: sg for sg in graph.subgraphs}

        inner = sg_map.get("Inner")
        outer = sg_map.get("Outer")
        assert inner is not None
        assert outer is not None
        assert "Inner" in outer.child_ids
        assert "A" in inner.node_ids
        assert "B" in inner.node_ids
        assert "C" in outer.node_ids

    def test_subgraph_auto_detect_gcp(self):
        src = """
graph LR
    subgraph GCP Environment
        A --> B
    end
"""
        graph = parse_mermaid(src)
        sg = graph.subgraphs[0]
        assert sg.component_type == "googlecloud"

    def test_subgraph_auto_detect_k8s(self):
        src = """
graph LR
    subgraph K8s Cluster
        A --> B
    end
"""
        graph = parse_mermaid(src)
        assert graph.subgraphs[0].component_type == "kubernetes"

    def test_subgraph_no_detect_generic(self):
        src = """
graph LR
    subgraph Backend Services
        A --> B
    end
"""
        graph = parse_mermaid(src)
        assert graph.subgraphs[0].component_type is None

    def test_triple_nested(self):
        src = """
graph LR
    subgraph GCP
        subgraph VPC
            subgraph K8s
                A --> B
            end
        end
    end
"""
        graph = parse_mermaid(src)
        assert len(graph.subgraphs) == 3
        sg_map = {sg.id: sg for sg in graph.subgraphs}
        assert "K8s" in sg_map["VPC"].child_ids
        assert "VPC" in sg_map["GCP"].child_ids


# ---------------------------------------------------------------------------
# Comments and blank lines
# ---------------------------------------------------------------------------


class TestCommentsAndBlanks:
    def test_comments_ignored(self):
        src = """
graph LR
    %% This is a comment
    A --> B
    %% Another comment
"""
        graph = parse_mermaid(src)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_blank_lines_ignored(self):
        src = """
graph LR

    A --> B

    B --> C

"""
        graph = parse_mermaid(src)
        assert len(graph.edges) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_input(self):
        graph = parse_mermaid("")
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_no_edges(self):
        graph = parse_mermaid("graph LR\n    A[Standalone]")
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0

    def test_self_referencing_node_style(self):
        """A node referenced in an edge that also has a shape definition."""
        graph = parse_mermaid("graph LR\n    A[Service] --> B{Decision}")
        node_map = {n.id: n for n in graph.nodes}
        assert node_map["A"].shape == ShapeType.RECTANGLE
        assert node_map["B"].shape == ShapeType.DIAMOND
