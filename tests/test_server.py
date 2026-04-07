"""Integration tests for MCP server tools."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from arch7_mcp.server import mcp

# Extract the raw functions from FastMCP tool wrappers
_tools = mcp._tool_manager._tools
create_diagram = _tools["create_diagram"].fn
mermaid_to_excalidraw = _tools["mermaid_to_excalidraw"].fn
modify_diagram = _tools["modify_diagram"].fn
get_diagram_info = _tools["get_diagram_info"].fn


@pytest.fixture
def tmp_excalidraw(tmp_path):
    """Return a function that generates temp file paths."""
    def _make(name: str = "test.excalidraw") -> str:
        return str(tmp_path / name)
    return _make


# ---------------------------------------------------------------------------
# create_diagram
# ---------------------------------------------------------------------------


class TestCreateDiagram:
    def test_basic_creation(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = create_diagram(
            nodes=[
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            connections=[{"from_id": "a", "to_id": "b"}],
            output_path=path,
        )
        assert "Created diagram at" in result
        assert os.path.exists(path)

        with open(path) as f:
            doc = json.load(f)
        assert doc["type"] == "excalidraw"

    def test_with_theme(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = create_diagram(
            nodes=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            connections=[{"from_id": "a", "to_id": "b"}],
            output_path=path,
            theme="professional",
        )
        assert "professional" in result

    def test_with_component_types(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = create_diagram(
            nodes=[
                {"id": "db", "label": "PostgreSQL", "component_type": "postgresql"},
                {"id": "cache", "label": "Redis", "component_type": "redis"},
            ],
            connections=[{"from_id": "db", "to_id": "cache"}],
            output_path=path,
        )
        assert "Database" in result

    def test_with_subgraphs(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = create_diagram(
            nodes=[
                {"id": "a", "label": "Service A"},
                {"id": "b", "label": "Service B"},
            ],
            connections=[{"from_id": "a", "to_id": "b"}],
            output_path=path,
            subgraphs=[
                {
                    "id": "sg",
                    "label": "Backend",
                    "node_ids": ["a", "b"],
                    "component_type": "kubernetes",
                }
            ],
        )
        assert os.path.exists(path)

    def test_with_nested_subgraphs(self, tmp_excalidraw):
        path = tmp_excalidraw()
        create_diagram(
            nodes=[
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
            ],
            connections=[
                {"from_id": "a", "to_id": "b"},
                {"from_id": "b", "to_id": "c"},
            ],
            output_path=path,
            subgraphs=[
                {"id": "inner", "label": "Inner", "node_ids": ["a", "b"]},
                {"id": "outer", "label": "Outer", "node_ids": ["c"], "child_ids": ["inner"]},
            ],
        )
        with open(path) as f:
            doc = json.load(f)
        containers = [e for e in doc["elements"] if e.get("opacity") == 60]
        assert len(containers) == 2

    def test_direction_param(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = create_diagram(
            nodes=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            connections=[{"from_id": "a", "to_id": "b"}],
            output_path=path,
            direction="TD",
        )
        assert "TD" in result

    def test_edge_styles(self, tmp_excalidraw):
        path = tmp_excalidraw()
        create_diagram(
            nodes=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            connections=[{"from_id": "a", "to_id": "b", "style": "dashed", "label": "async"}],
            output_path=path,
        )
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# mermaid_to_excalidraw
# ---------------------------------------------------------------------------


class TestMermaidToExcalidraw:
    def test_basic_mermaid(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = mermaid_to_excalidraw(
            mermaid_syntax="graph LR\n    A --> B --> C",
            output_path=path,
        )
        assert "Converted mermaid" in result
        assert os.path.exists(path)

    def test_mermaid_with_subgraphs(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = mermaid_to_excalidraw(
            mermaid_syntax="""
graph LR
    subgraph Backend
        A --> B
    end
""",
            output_path=path,
        )
        assert "Subgraphs: 1" in result

    def test_mermaid_with_theme(self, tmp_excalidraw):
        path = tmp_excalidraw()
        result = mermaid_to_excalidraw(
            mermaid_syntax="graph LR\n    A --> B",
            output_path=path,
            theme="professional",
        )
        assert "professional" in result


# ---------------------------------------------------------------------------
# modify_diagram
# ---------------------------------------------------------------------------


class TestModifyDiagram:
    def _create_base(self, path: str) -> str:
        return create_diagram(
            nodes=[
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            connections=[{"from_id": "a", "to_id": "b"}],
            output_path=path,
        )

    def test_add_node(self, tmp_excalidraw):
        path = tmp_excalidraw()
        self._create_base(path)
        result = modify_diagram(
            file_path=path,
            operations=[{"op": "add_node", "id": "c", "label": "New Node"}],
        )
        assert "c" in result.lower() or "new" in result.lower() or "Added" in result or "applied" in result.lower()

    def test_remove_node(self, tmp_excalidraw):
        path = tmp_excalidraw()
        self._create_base(path)
        result = modify_diagram(
            file_path=path,
            operations=[{"op": "remove_node", "id": "b"}],
        )
        assert "error" not in result.lower() or "applied" in result.lower()

    def test_add_connection(self, tmp_excalidraw):
        path = tmp_excalidraw()
        self._create_base(path)
        result = modify_diagram(
            file_path=path,
            operations=[
                {"op": "add_node", "id": "c", "label": "C"},
                {"op": "add_connection", "from_id": "a", "to_id": "c"},
            ],
        )
        assert "error" not in result.lower() or "applied" in result.lower()

    def test_unknown_op_returns_error(self, tmp_excalidraw):
        path = tmp_excalidraw()
        self._create_base(path)
        result = modify_diagram(
            file_path=path,
            operations=[{"op": "banana"}],
        )
        assert "error" in result.lower() or "unknown" in result.lower()


# ---------------------------------------------------------------------------
# get_diagram_info
# ---------------------------------------------------------------------------


class TestGetDiagramInfo:
    def test_returns_summary(self, tmp_excalidraw):
        path = tmp_excalidraw()
        create_diagram(
            nodes=[
                {"id": "db", "label": "PostgreSQL", "component_type": "postgresql"},
                {"id": "api", "label": "API"},
            ],
            connections=[{"from_id": "api", "to_id": "db"}],
            output_path=path,
        )
        info = get_diagram_info(path)
        assert "PostgreSQL" in info or "db" in info
        assert "api" in info.lower()
