"""Lenient parsing helpers for LLM-supplied enum and ID fields.

LLMs regularly pass values like ``"square"`` for a shape or ``"dashdot"``
for an edge style. Rather than crashing with a Pydantic/enum error, these
helpers return a sensible fallback and append a human-readable warning
to an accumulator list that the MCP tool can surface in its response.
"""

from __future__ import annotations

from arch7_mcp.core.models import Direction, EdgeStyle, ShapeType

# ---------------------------------------------------------------------------
# Enum parsing with fallback
# ---------------------------------------------------------------------------

_SHAPE_ALIASES: dict[str, ShapeType] = {
    "square": ShapeType.RECTANGLE,
    "box": ShapeType.RECTANGLE,
    "rect": ShapeType.RECTANGLE,
    "rhombus": ShapeType.DIAMOND,
    "oval": ShapeType.ELLIPSE,
    "pill": ShapeType.STADIUM,
    "database": ShapeType.CYLINDER_V,
    "db": ShapeType.CYLINDER_V,
    "queue": ShapeType.CYLINDER_H,
    "topic": ShapeType.CYLINDER_H,
}

_EDGE_ALIASES: dict[str, EdgeStyle] = {
    "dash": EdgeStyle.DASHED,
    "dot": EdgeStyle.DOTTED,
    "bold": EdgeStyle.THICK,
    "heavy": EdgeStyle.THICK,
}

_DIRECTION_ALIASES: dict[str, Direction] = {
    "horizontal": Direction.LEFT_RIGHT,
    "vertical": Direction.TOP_DOWN,
    "left-right": Direction.LEFT_RIGHT,
    "top-down": Direction.TOP_DOWN,
    "top-bottom": Direction.TOP_DOWN,
    "bottom-top": Direction.BOTTOM_UP,
    "right-left": Direction.RIGHT_LEFT,
}


def parse_shape_type(
    value: str | None,
    warnings: list[str] | None = None,
    context: str = "",
) -> ShapeType:
    """Parse a shape string with aliases and fallback to RECTANGLE."""
    if not value:
        return ShapeType.RECTANGLE
    key = value.lower().strip()
    try:
        return ShapeType(key)
    except ValueError:
        pass
    if key in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[key]
    if warnings is not None:
        prefix = f"{context}: " if context else ""
        warnings.append(f"{prefix}unknown shape '{value}', using rectangle")
    return ShapeType.RECTANGLE


def parse_edge_style(
    value: str | None,
    warnings: list[str] | None = None,
    context: str = "",
) -> EdgeStyle:
    """Parse an edge-style string with aliases and fallback to SOLID."""
    if not value:
        return EdgeStyle.SOLID
    key = value.lower().strip()
    try:
        return EdgeStyle(key)
    except ValueError:
        pass
    if key in _EDGE_ALIASES:
        return _EDGE_ALIASES[key]
    if warnings is not None:
        prefix = f"{context}: " if context else ""
        warnings.append(f"{prefix}unknown edge style '{value}', using solid")
    return EdgeStyle.SOLID


def parse_direction(
    value: str | None,
    warnings: list[str] | None = None,
) -> Direction:
    """Parse a direction string with aliases and fallback to LR."""
    if not value:
        return Direction.LEFT_RIGHT
    key = value.upper().strip()
    try:
        return Direction(key)
    except ValueError:
        pass
    if key.lower() in _DIRECTION_ALIASES:
        return _DIRECTION_ALIASES[key.lower()]
    if warnings is not None:
        warnings.append(f"unknown direction '{value}', using LR")
    return Direction.LEFT_RIGHT


# ---------------------------------------------------------------------------
# Graph structural validation
# ---------------------------------------------------------------------------


class DiagramInputError(ValueError):
    """Raised for unrecoverable issues in user-supplied node/connection data."""


def validate_node_ids(nodes: list[dict]) -> None:
    """Ensure node IDs are non-empty, unique, and whitespace-free."""
    seen: set[str] = set()
    for i, n in enumerate(nodes):
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            raise DiagramInputError(f"node[{i}]: id must be a non-empty string")
        if nid != nid.strip() or " " in nid:
            raise DiagramInputError(
                f"node[{i}]: id '{nid}' must not contain whitespace"
            )
        if nid in seen:
            raise DiagramInputError(f"duplicate node id '{nid}'")
        seen.add(nid)


def filter_orphan_connections(
    connections: list[dict],
    node_ids: set[str],
    warnings: list[str],
) -> list[dict]:
    """Drop connections whose endpoints don't exist, warning for each."""
    kept: list[dict] = []
    for i, c in enumerate(connections):
        src = c.get("from_id")
        dst = c.get("to_id")
        if src not in node_ids:
            warnings.append(f"connection[{i}]: unknown from_id '{src}', skipped")
            continue
        if dst not in node_ids:
            warnings.append(f"connection[{i}]: unknown to_id '{dst}', skipped")
            continue
        kept.append(c)
    return kept
