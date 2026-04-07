"""Tests for the Excalidraw renderer and themes."""

from __future__ import annotations

import json

import pytest

from arch7_mcp.core.models import Direction, ThemeName
from arch7_mcp.core.themes import THEMES, Theme, get_theme
from arch7_mcp.engine.layout import compute_layout
from arch7_mcp.engine.renderer import build_excalidraw_file


# ---------------------------------------------------------------------------
# Theme system
# ---------------------------------------------------------------------------


class TestThemes:
    def test_all_themes_exist(self):
        for name in ThemeName:
            assert name in THEMES

    def test_get_theme_by_string(self):
        theme = get_theme("professional")
        assert theme.name == ThemeName.PROFESSIONAL

    def test_get_theme_fallback(self):
        theme = get_theme("nonexistent")
        assert theme.name == ThemeName.DEFAULT

    def test_professional_theme_clean(self):
        theme = get_theme("professional")
        assert theme.roughness == 0
        assert theme.font_family == 2  # Helvetica

    def test_default_theme_sketchy(self):
        theme = get_theme("default")
        assert theme.roughness == 1
        assert theme.font_family == 1  # Virgil

    def test_dark_theme_inverts(self):
        theme = get_theme("dark")
        assert theme.invert_component_colors is True


# ---------------------------------------------------------------------------
# Excalidraw output structure
# ---------------------------------------------------------------------------


class TestExcalidrawOutput:
    def test_valid_structure(self, simple_graph):
        layout = compute_layout(simple_graph)
        doc = build_excalidraw_file(layout)
        assert doc["type"] == "excalidraw"
        assert doc["version"] == 2
        assert "elements" in doc
        assert "appState" in doc
        assert "files" in doc

    def test_elements_have_required_fields(self, simple_graph):
        layout = compute_layout(simple_graph)
        doc = build_excalidraw_file(layout)
        for el in doc["elements"]:
            assert "id" in el
            assert "type" in el
            assert "x" in el
            assert "y" in el

    def test_output_is_json_serializable(self, simple_graph):
        layout = compute_layout(simple_graph)
        doc = build_excalidraw_file(layout)
        serialized = json.dumps(doc)
        assert len(serialized) > 0


# ---------------------------------------------------------------------------
# Theme propagation
# ---------------------------------------------------------------------------


class TestThemePropagation:
    def test_professional_roughness_zero(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        for el in doc["elements"]:
            r = el.get("roughness")
            if r is not None:
                assert r == 0, f"Element {el['id']} has roughness={r} (expected 0)"

    def test_professional_font_helvetica(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        for el in doc["elements"]:
            ff = el.get("fontFamily")
            if ff is not None:
                assert ff == 2, f"Element {el['id']} has fontFamily={ff} (expected 2)"

    def test_default_font_virgil(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout, theme_name="default")
        for el in doc["elements"]:
            ff = el.get("fontFamily")
            if ff is not None:
                assert ff == 1, f"Element {el['id']} has fontFamily={ff} (expected 1)"

    def test_canvas_background_matches_theme(self, simple_graph):
        layout = compute_layout(simple_graph)
        for theme_name in ["default", "dark", "professional"]:
            doc = build_excalidraw_file(layout, theme_name=theme_name)
            theme = get_theme(theme_name)
            assert doc["appState"]["viewBackgroundColor"] == theme.canvas_background


# ---------------------------------------------------------------------------
# Subgraph containers
# ---------------------------------------------------------------------------


class TestSubgraphRendering:
    def test_containers_rendered(self, nested_subgraph_graph):
        layout = compute_layout(nested_subgraph_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        container_els = [e for e in doc["elements"] if e.get("opacity") == 60]
        assert len(container_els) == 2  # k8s + gcp

    def test_nested_parent_wraps_child(self, nested_subgraph_graph):
        layout = compute_layout(nested_subgraph_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        containers = [e for e in doc["elements"] if e.get("opacity") == 60]
        # Sort by area (larger = parent)
        containers.sort(key=lambda e: e["width"] * e["height"], reverse=True)
        parent, child = containers[0], containers[1]
        # Parent should fully contain child
        assert parent["x"] <= child["x"]
        assert parent["y"] <= child["y"]
        assert parent["x"] + parent["width"] >= child["x"] + child["width"]
        assert parent["y"] + parent["height"] >= child["y"] + child["height"]

    def test_container_has_label_text(self, nested_subgraph_graph):
        layout = compute_layout(nested_subgraph_graph)
        doc = build_excalidraw_file(layout)
        text_els = [e for e in doc["elements"] if e.get("type") == "text"]
        texts = {e["text"] for e in text_els}
        assert "GKE Cluster" in texts
        assert "Google Cloud" in texts


# ---------------------------------------------------------------------------
# Icons in output
# ---------------------------------------------------------------------------


class TestIconRendering:
    def test_typed_nodes_have_icons(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        image_els = [e for e in doc["elements"] if e["type"] == "image"]
        assert len(image_els) >= 4  # nginx, postgresql, redis, kafka

    def test_icon_files_populated(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout)
        assert len(doc["files"]) >= 4

    def test_icon_file_ids_match(self, typed_graph):
        layout = compute_layout(typed_graph)
        doc = build_excalidraw_file(layout)
        for el in doc["elements"]:
            if el["type"] == "image":
                file_id = el["fileId"]
                assert file_id in doc["files"], f"Image references missing file {file_id}"

    def test_subgraph_icon_rendered(self, nested_subgraph_graph):
        layout = compute_layout(nested_subgraph_graph)
        doc = build_excalidraw_file(layout, theme_name="professional")
        image_els = [e for e in doc["elements"] if e["type"] == "image"]
        # Should have node icons + container icons (k8s, gcp)
        icon_sizes = {e["width"] for e in image_els}
        assert 32 in icon_sizes  # container icons are 32x32
        assert 28 in icon_sizes  # node icons are 28x28

    def test_no_icons_for_untyped_graph(self):
        from arch7_mcp.core.models import DiagramGraph, Edge, Node

        graph = DiagramGraph(
            nodes=[Node(id="a", label="Foo"), Node(id="b", label="Bar")],
            edges=[Edge(from_id="a", to_id="b")],
        )
        layout = compute_layout(graph)
        doc = build_excalidraw_file(layout)
        image_els = [e for e in doc["elements"] if e["type"] == "image"]
        assert len(image_els) == 0
        assert len(doc["files"]) == 0


# ---------------------------------------------------------------------------
# Arrow bindings
# ---------------------------------------------------------------------------


class TestArrowBindings:
    def test_arrows_have_bindings(self, simple_graph):
        layout = compute_layout(simple_graph)
        doc = build_excalidraw_file(layout)
        arrows = [e for e in doc["elements"] if e["type"] == "arrow"]
        for arrow in arrows:
            assert arrow.get("startBinding") is not None or arrow.get("endBinding") is not None

    def test_arrow_start_end_arrowheads(self, simple_graph):
        layout = compute_layout(simple_graph)
        doc = build_excalidraw_file(layout)
        arrows = [e for e in doc["elements"] if e["type"] == "arrow"]
        for arrow in arrows:
            assert arrow["startArrowhead"] is None
            assert arrow["endArrowhead"] == "arrow"
