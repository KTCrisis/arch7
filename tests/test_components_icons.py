"""Tests for component detection and icon registry."""

from __future__ import annotations

import pytest

from arch7_mcp.core.components import (
    DEFAULT_STYLE,
    ComponentStyle,
    detect_component,
    list_components,
)
from arch7_mcp.core.icons import (
    _COMPONENT_TO_ICON,
    _ICON_PATHS,
    get_icon_data_url,
    has_icon,
)
from arch7_mcp.core.models import ShapeType


# ---------------------------------------------------------------------------
# Component detection
# ---------------------------------------------------------------------------


class TestDetectComponent:
    def test_explicit_type_exact_match(self):
        style = detect_component("My DB", "postgresql")
        assert style.category == "Database"
        assert style.shape == ShapeType.CYLINDER_V

    def test_explicit_type_case_insensitive(self):
        style = detect_component("whatever", "PostgreSQL")
        assert style.category == "Database"

    def test_label_auto_detection(self):
        style = detect_component("Redis Cache")
        assert style.category == "Cache"

    def test_label_token_match(self):
        style = detect_component("kafka")
        assert style.category == "Message Queue"

    def test_label_substring_match(self):
        style = detect_component("my-postgresql-db")
        assert style.category == "Database"

    def test_unknown_returns_default(self):
        style = detect_component("Unknown Widget")
        assert style is DEFAULT_STYLE
        assert style.shape == ShapeType.RECTANGLE

    def test_default_has_no_badge(self):
        assert DEFAULT_STYLE.badge == ""

    @pytest.mark.parametrize(
        "component_type, expected_shape",
        [
            ("postgresql", ShapeType.CYLINDER_V),
            ("mongodb", ShapeType.CYLINDER_V),
            ("kafka", ShapeType.CYLINDER_H),
            ("rabbitmq", ShapeType.CYLINDER_H),
            ("agent", ShapeType.DIAMOND),
            ("llm", ShapeType.ELLIPSE),
            ("nginx", ShapeType.RECTANGLE),
        ],
    )
    def test_shape_for_component(self, component_type: str, expected_shape: ShapeType):
        style = detect_component("x", component_type)
        assert style.shape == expected_shape

    def test_explicit_type_overrides_label(self):
        """Explicit component_type takes priority over label detection."""
        style = detect_component("Redis", "postgresql")
        assert style.category == "Database"  # postgresql wins over redis label


class TestListComponents:
    def test_returns_categories(self):
        cats = list_components()
        assert isinstance(cats, dict)
        assert "Database" in cats
        assert "Message Queue" in cats

    def test_no_empty_categories(self):
        for cat, names in list_components().items():
            assert len(names) > 0, f"Category {cat} is empty"


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------


class TestIconRegistry:
    def test_icon_count(self):
        assert len(_ICON_PATHS) >= 50

    def test_mapping_count(self):
        assert len(_COMPONENT_TO_ICON) >= 90

    def test_all_mappings_point_to_existing_icons(self):
        for comp, slug in _COMPONENT_TO_ICON.items():
            assert slug in _ICON_PATHS, f"Mapping '{comp}' -> '{slug}' but '{slug}' not in _ICON_PATHS"


class TestHasIcon:
    @pytest.mark.parametrize(
        "label, component_type",
        [
            ("PostgreSQL", None),
            ("Redis Cache", None),
            ("Kafka", None),
            ("My Service", "nginx"),
            ("GKE Cluster", "gke"),
            ("Lambda", "lambda"),
            ("EC2 Instance", "ec2"),
        ],
    )
    def test_has_icon_true(self, label: str, component_type: str | None):
        assert has_icon(label, component_type) is True

    def test_has_icon_false_for_unknown(self):
        assert has_icon("Unknown Widget") is False

    def test_has_icon_false_for_generic_service(self):
        assert has_icon("My Service") is False


class TestGetIconDataUrl:
    def test_returns_data_url(self):
        url = get_icon_data_url("PostgreSQL")
        assert url is not None
        assert url.startswith("data:image/svg+xml;base64,")

    def test_returns_none_for_unknown(self):
        assert get_icon_data_url("Unknown Widget") is None

    def test_data_url_is_valid_base64(self):
        import base64

        url = get_icon_data_url("Redis", "redis")
        assert url is not None
        b64_part = url.split(",", 1)[1]
        decoded = base64.b64decode(b64_part).decode("utf-8")
        assert "<svg" in decoded
        assert "path" in decoded

    def test_caching(self):
        """Calling twice returns the same object."""
        url1 = get_icon_data_url("Docker", "docker")
        url2 = get_icon_data_url("Docker", "docker")
        assert url1 is url2

    @pytest.mark.parametrize(
        "component_type",
        ["aws", "azure", "lambda", "dynamodb", "sqs", "ec2", "ecs"],
    )
    def test_custom_cloud_icons_exist(self, component_type: str):
        url = get_icon_data_url("x", component_type)
        assert url is not None, f"No icon for custom component '{component_type}'"
