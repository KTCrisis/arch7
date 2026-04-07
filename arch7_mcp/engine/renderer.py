"""Excalidraw JSON element builder.

Converts LayoutResult (positioned nodes and edges) into a valid .excalidraw
file with proper element bindings, component-aware styling, and embedded
metadata for stateful editing.
"""

from __future__ import annotations

import json
import math
import random
import uuid
from pathlib import Path
from typing import Any

from arch7_mcp.core.components import DEFAULT_STYLE, detect_component
from arch7_mcp.core.icons import get_icon_data_url, has_icon
from arch7_mcp.core.models import (
    ConnectionMetadata,
    DiagramMetadata,
    Direction,
    EdgeStyle,
    LayoutResult,
    NodeMetadata,
    PositionedEdge,
    PositionedNode,
    ShapeType,
    Subgraph,
    ThemeName,
)
from arch7_mcp.core.themes import Theme, darken_hex, get_theme

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXCALIDRAW_VERSION = 2
EXCALIDRAW_SOURCE = "https://github.com/bhukyavenkatesh/excalidraw-architect-mcp"

FONT_SIZE = 16
DEFAULT_FONT_FAMILY = 1  # 1 = Virgil (hand-drawn), 2 = Helvetica, 3 = Cascadia
BADGE_FONT_SIZE = 12
ICON_SIZE = 28
ICON_GAP = 6

# Approximate character widths per font family (pixels per character at fontSize=1).
# These are empirical averages; Excalidraw uses canvas measureText internally
# but we need reasonable estimates for raw JSON generation.
_CHAR_WIDTH_FACTORS: dict[int, float] = {
    1: 0.55,  # Virgil (hand-drawn) - wider glyphs
    2: 0.50,  # Helvetica
    3: 0.55,  # Cascadia (monospace)
}
_LINE_HEIGHT = 1.25


# ---------------------------------------------------------------------------
# Text measurement
# ---------------------------------------------------------------------------


def _measure_text(
    text: str, font_size: int = FONT_SIZE, font_family: int = DEFAULT_FONT_FAMILY
) -> tuple[float, float]:
    """Estimate rendered text dimensions in pixels.

    Returns (width, height).
    """
    factor = _CHAR_WIDTH_FACTORS.get(font_family, 0.55)
    lines = text.split("\n")
    max_chars = max(len(line) for line in lines) if lines else 0
    width = max_chars * font_size * factor
    height = len(lines) * font_size * _LINE_HEIGHT
    return round(max(width, 10), 2), round(max(height, font_size * _LINE_HEIGHT), 2)


# ---------------------------------------------------------------------------
# ID / seed generation
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:20]


def _seed() -> int:
    return random.randint(1, 2_000_000_000)


def _nonce() -> int:
    return random.randint(1, 2_000_000_000)


# ---------------------------------------------------------------------------
# Base element factory
# ---------------------------------------------------------------------------


def _base_element(
    element_type: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    stroke_color: str = "#1e1e1e",
    background_color: str = "transparent",
    fill_style: str = "solid",
    stroke_width: int = 2,
    stroke_style: str = "solid",
    roughness: int | None = None,
    opacity: int = 100,
    element_id: str | None = None,
    custom_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a base Excalidraw element with all required fields."""
    el: dict[str, Any] = {
        "id": element_id or _uid(),
        "type": element_type,
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(width, 2),
        "height": round(height, 2),
        "angle": 0,
        "strokeColor": stroke_color,
        "backgroundColor": background_color,
        "fillStyle": fill_style,
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "roughness": roughness if roughness is not None else 1,
        "opacity": opacity,
        "groupIds": [],
        "frameId": None,
        "index": None,
        "roundness": {"type": 3},
        "seed": _seed(),
        "version": 1,
        "versionNonce": _nonce(),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }
    if custom_data:
        el["customData"] = custom_data
    return el


# ---------------------------------------------------------------------------
# Shape elements
# ---------------------------------------------------------------------------


def _excalidraw_shape_type(shape: ShapeType) -> str:
    """Map our ShapeType enum to excalidraw element types."""
    match shape:
        case ShapeType.DIAMOND:
            return "diamond"
        case ShapeType.ELLIPSE | ShapeType.CIRCLE:
            return "ellipse"
        case ShapeType.CYLINDER_V | ShapeType.CYLINDER_H:
            return "cylinder"  # handled specially in _make_shape
        case _:
            return "rectangle"


# ---------------------------------------------------------------------------
# Cylinder shape builders
# ---------------------------------------------------------------------------


def _make_cylinder_v(
    x: float, y: float, w: float, h: float,
    stroke_color: str, group_id: str,
    roughness: int = 1,
) -> list[dict[str, Any]]:
    """Build a vertical cylinder (database) from lines + ellipse.

    Structure: body (closed line), two band lines, top ellipse cap.
    """
    elements: list[dict[str, Any]] = []
    cap_h = min(h * 0.15, 12)  # ellipse cap height

    # Body: closed rectangle-ish shape with curved top/bottom
    body = _base_element("line", x, y + cap_h / 2, w, h - cap_h / 2,
                         stroke_color=stroke_color, roughness=roughness)
    body["groupIds"] = [group_id]
    body["roundness"] = {"type": 2}
    body["points"] = [
        [0, 0],
        [0, h - cap_h],
        [0, h - cap_h / 2],
        [w * 0.15, h],
        [w * 0.5, h + cap_h * 0.1],
        [w * 0.85, h],
        [w, h - cap_h / 2],
        [w, h - cap_h],
        [w, 0],
        [w, -cap_h * 0.3],
        [w * 0.85, -cap_h * 0.7],
        [w * 0.5, -cap_h * 0.85],
        [w * 0.15, -cap_h * 0.7],
        [0, -cap_h * 0.3],
        [0, 0],
    ]
    body["lastCommittedPoint"] = None
    body["startBinding"] = None
    body["endBinding"] = None
    body["startArrowhead"] = None
    body["endArrowhead"] = None
    body.pop("type", None)
    body["type"] = "line"
    elements.append(body)

    # Band line 1
    band1_y = y + cap_h / 2 + (h - cap_h) * 0.3
    band1 = _base_element("line", x, band1_y, w, cap_h * 0.6,
                          stroke_color=stroke_color, stroke_width=1, roughness=roughness)
    band1["groupIds"] = [group_id]
    band1["roundness"] = {"type": 2}
    band1["points"] = [
        [0, 0],
        [w * 0.15, cap_h * 0.4],
        [w * 0.5, cap_h * 0.6],
        [w * 0.85, cap_h * 0.4],
        [w, 0],
    ]
    band1["lastCommittedPoint"] = None
    band1["startBinding"] = None
    band1["endBinding"] = None
    band1["startArrowhead"] = None
    band1["endArrowhead"] = None
    band1.pop("type", None)
    band1["type"] = "line"
    elements.append(band1)

    # Band line 2
    band2_y = y + cap_h / 2 + (h - cap_h) * 0.55
    band2 = _base_element("line", x, band2_y, w, cap_h * 0.5,
                          stroke_color=stroke_color, stroke_width=1, roughness=roughness)
    band2["groupIds"] = [group_id]
    band2["roundness"] = {"type": 2}
    band2["points"] = [
        [0, 0],
        [w * 0.15, cap_h * 0.35],
        [w * 0.5, cap_h * 0.5],
        [w * 0.85, cap_h * 0.35],
        [w, 0],
    ]
    band2["lastCommittedPoint"] = None
    band2["startBinding"] = None
    band2["endBinding"] = None
    band2["startArrowhead"] = None
    band2["endArrowhead"] = None
    band2.pop("type", None)
    band2["type"] = "line"
    elements.append(band2)

    # Top ellipse cap
    cap = _base_element("ellipse", x, y, w, cap_h,
                        stroke_color=stroke_color, roughness=roughness)
    cap["groupIds"] = [group_id]
    cap["roundness"] = None
    elements.append(cap)

    return elements


def _make_cylinder_h(
    x: float, y: float, w: float, h: float,
    stroke_color: str, group_id: str,
    roughness: int = 1,
) -> list[dict[str, Any]]:
    """Build a horizontal cylinder (topic/queue) from lines + ellipse.

    Same as vertical but rotated — cap on the right side.
    """
    elements: list[dict[str, Any]] = []
    cap_w = min(w * 0.2, 14)  # ellipse cap width

    # Body
    body = _base_element("line", x, y, w - cap_w / 2, h,
                         stroke_color=stroke_color, roughness=roughness)
    body["groupIds"] = [group_id]
    body["roundness"] = {"type": 2}
    body["points"] = [
        [0, 0],
        [w - cap_w, 0],
        [w - cap_w / 2, 0],
        [w, h * 0.15],
        [w + cap_w * 0.1, h * 0.5],
        [w, h * 0.85],
        [w - cap_w / 2, h],
        [w - cap_w, h],
        [0, h],
        [-cap_w * 0.3, h],
        [-cap_w * 0.7, h * 0.85],
        [-cap_w * 0.85, h * 0.5],
        [-cap_w * 0.7, h * 0.15],
        [-cap_w * 0.3, 0],
        [0, 0],
    ]
    body["lastCommittedPoint"] = None
    body["startBinding"] = None
    body["endBinding"] = None
    body["startArrowhead"] = None
    body["endArrowhead"] = None
    body.pop("type", None)
    body["type"] = "line"
    elements.append(body)

    # Band line 1
    band1_x = x + (w - cap_w) * 0.35
    band1 = _base_element("line", band1_x, y, cap_w * 0.6, h,
                          stroke_color=stroke_color, stroke_width=1, roughness=roughness)
    band1["groupIds"] = [group_id]
    band1["roundness"] = {"type": 2}
    band1["points"] = [
        [0, 0],
        [cap_w * 0.4, h * 0.15],
        [cap_w * 0.6, h * 0.5],
        [cap_w * 0.4, h * 0.85],
        [0, h],
    ]
    band1["lastCommittedPoint"] = None
    band1["startBinding"] = None
    band1["endBinding"] = None
    band1["startArrowhead"] = None
    band1["endArrowhead"] = None
    band1.pop("type", None)
    band1["type"] = "line"
    elements.append(band1)

    # Band line 2
    band2_x = x + (w - cap_w) * 0.55
    band2 = _base_element("line", band2_x, y, cap_w * 0.5, h,
                          stroke_color=stroke_color, stroke_width=1, roughness=roughness)
    band2["groupIds"] = [group_id]
    band2["roundness"] = {"type": 2}
    band2["points"] = [
        [0, 0],
        [cap_w * 0.35, h * 0.15],
        [cap_w * 0.5, h * 0.5],
        [cap_w * 0.35, h * 0.85],
        [0, h],
    ]
    band2["lastCommittedPoint"] = None
    band2["startBinding"] = None
    band2["endBinding"] = None
    band2["startArrowhead"] = None
    band2["endArrowhead"] = None
    band2.pop("type", None)
    band2["type"] = "line"
    elements.append(band2)

    # Left ellipse cap
    cap = _base_element("ellipse", x - cap_w / 2, y, cap_w, h,
                        stroke_color=stroke_color, roughness=roughness)
    cap["groupIds"] = [group_id]
    cap["roundness"] = None
    elements.append(cap)

    return elements


def _make_shape(
    pn: PositionedNode,
    theme: Theme,
    files: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the shape element + bound text + optional badge + optional icon.

    Returns (shape_element, [extra_elements]).
    If *files* dict is provided, icon file entries are added to it.
    """
    node = pn.node
    style = detect_component(node.label, node.component_type)
    has_badge = bool(style.badge)

    bg_color = style.background_color if style != DEFAULT_STYLE else theme.default_bg
    st_color = style.stroke_color if style != DEFAULT_STYLE else theme.default_stroke
    text_color = theme.default_text

    if theme.invert_component_colors and style != DEFAULT_STYLE:
        bg_color = darken_hex(style.background_color, 0.55)
        st_color = style.stroke_color

    resolved_shape = style.shape if style != DEFAULT_STYLE else node.shape
    is_cylinder = resolved_shape in (ShapeType.CYLINDER_V, ShapeType.CYLINDER_H)

    shape_id = _uid()
    # For cylinders, we still create a transparent rectangle as the main
    # bounding element (for arrow bindings), then overlay the visual cylinder
    shape_type = "rectangle" if is_cylinder else _excalidraw_shape_type(resolved_shape)

    shape_el = _base_element(
        shape_type,
        pn.x,
        pn.y,
        pn.width,
        pn.height,
        stroke_color=st_color if not is_cylinder else "transparent",
        background_color=bg_color if not is_cylinder else "transparent",
        roughness=theme.roughness,
        element_id=shape_id,
        custom_data={"node_id": node.id},
    )
    if is_cylinder:
        shape_el["strokeWidth"] = 0
        shape_el["opacity"] = 0

    extra_elements: list[dict[str, Any]] = []

    # -- Main label text (bound to shape) --
    font_family = theme.font_family
    label_w, label_h = _measure_text(node.label, FONT_SIZE, font_family)
    label_id = _uid()
    label_x = pn.x + (pn.width - label_w) / 2
    label_y = pn.y + (pn.height - label_h) / 2
    if has_badge:
        label_y += (BADGE_FONT_SIZE + 4) / 2

    label_el = _base_element(
        "text",
        label_x,
        label_y,
        label_w,
        label_h,
        stroke_color=text_color,
        roughness=theme.roughness,
        element_id=label_id,
    )
    label_el.update(
        {
            "text": node.label,
            "fontSize": FONT_SIZE,
            "fontFamily": font_family,
            "textAlign": "center",
            "verticalAlign": "middle",
            "containerId": shape_id,
            "originalText": node.label,
            "autoResize": True,
            "lineHeight": _LINE_HEIGHT,
        }
    )

    shape_el["boundElements"].append({"id": label_id, "type": "text"})
    extra_elements.append(label_el)

    # -- Badge (small rectangle with category text above the label) --
    if has_badge:
        badge_w, badge_h = _measure_text(style.badge, BADGE_FONT_SIZE, font_family)
        badge_w += 16  # padding
        badge_h += 6
        badge_x = pn.x + (pn.width - badge_w) / 2
        badge_y = pn.y + 6

        badge_shape = _base_element(
            "rectangle",
            badge_x,
            badge_y,
            badge_w,
            badge_h,
            stroke_color=st_color,
            background_color=theme.badge_bg,
            stroke_width=1,
            roughness=0,
        )
        badge_shape["roundness"] = {"type": 3}

        btw, bth = _measure_text(style.badge, BADGE_FONT_SIZE, font_family)
        badge_text_id = _uid()
        badge_text = _base_element(
            "text",
            badge_x + (badge_w - btw) / 2,
            badge_y + (badge_h - bth) / 2,
            btw,
            bth,
            stroke_color=theme.badge_text,
            roughness=theme.roughness,
            element_id=badge_text_id,
        )
        badge_text.update(
            {
                "text": style.badge,
                "fontSize": BADGE_FONT_SIZE,
                "fontFamily": font_family,
                "textAlign": "center",
                "verticalAlign": "middle",
                "containerId": badge_shape["id"],
                "originalText": style.badge,
                "autoResize": True,
                "lineHeight": _LINE_HEIGHT,
            }
        )
        badge_shape["boundElements"].append({"id": badge_text_id, "type": "text"})

        group_id = _uid()
        shape_el["groupIds"].append(group_id)
        badge_shape["groupIds"].append(group_id)
        badge_text["groupIds"].append(group_id)
        label_el["groupIds"].append(group_id)

        extra_elements.extend([badge_shape, badge_text])

    # -- Cylinder visual elements (overlaid on transparent bounding rect) --
    if is_cylinder:
        cyl_group_id = _uid()
        if resolved_shape == ShapeType.CYLINDER_V:
            cyl_els = _make_cylinder_v(
                pn.x, pn.y, pn.width, pn.height, st_color, cyl_group_id,
                roughness=theme.roughness,
            )
        else:
            cyl_els = _make_cylinder_h(
                pn.x, pn.y, pn.width, pn.height, st_color, cyl_group_id,
                roughness=theme.roughness,
            )
        extra_elements.extend(cyl_els)

    # -- Technology icon (image element, left of label) --
    icon_data_url = get_icon_data_url(node.label, node.component_type)
    if icon_data_url and files is not None:
        file_id = _uid()
        files[file_id] = {
            "mimeType": "image/svg+xml",
            "id": file_id,
            "dataURL": icon_data_url,
            "created": 1,
            "lastRetrieved": 1,
        }
        icon_x = pn.x + 10
        icon_y = pn.y + (pn.height - ICON_SIZE) / 2
        if has_badge:
            icon_y += 6

        icon_el = _base_element(
            "image",
            icon_x,
            icon_y,
            ICON_SIZE,
            ICON_SIZE,
            stroke_color="transparent",
            roughness=0,
        )
        icon_el["status"] = "saved"
        icon_el["fileId"] = file_id
        icon_el["scale"] = [1, 1]
        extra_elements.append(icon_el)

    return shape_el, extra_elements


# ---------------------------------------------------------------------------
# Arrow elements
# ---------------------------------------------------------------------------


def _stroke_style_for_edge(style: EdgeStyle) -> str:
    match style:
        case EdgeStyle.DASHED:
            return "dashed"
        case EdgeStyle.DOTTED:
            return "dotted"
        case _:
            return "solid"


def _stroke_width_for_edge(style: EdgeStyle) -> int:
    return 4 if style == EdgeStyle.THICK else 2


def _make_arrow(
    pe: PositionedEdge,
    node_elements: dict[str, dict[str, Any]],
    theme: Theme,
    direction: Direction,
    node_rects: dict[str, PositionedNode] | None = None,
) -> list[dict[str, Any]]:
    """Build an arrow element with optional label text.

    Arrow start/end points come from the layout engine (already at shape
    edges). Bindings use per-edge fixedPoints computed from source/target
    geometry so fan-out arrows depart at distinct positions on the hub.
    """
    edge = pe.edge
    arrow_id = _uid()

    if pe.points and len(pe.points) >= 2:
        origin = pe.points[0]
        arrow_x, arrow_y = round(origin[0], 2), round(origin[1], 2)
        points = [[round(p[0] - origin[0], 2), round(p[1] - origin[1], 2)] for p in pe.points]
    else:
        points = [[0, 0], [100, 0]]
        arrow_x, arrow_y = 0.0, 0.0

    all_px = [p[0] for p in points]
    all_py = [p[1] for p in points]
    bbox_w = max(all_px) - min(all_px)
    bbox_h = max(all_py) - min(all_py)

    arrow_el = _base_element(
        "arrow",
        arrow_x,
        arrow_y,
        max(bbox_w, 1),
        max(bbox_h, 1),
        stroke_color=theme.arrow_stroke,
        roughness=theme.roughness,
        element_id=arrow_id,
        stroke_style=_stroke_style_for_edge(edge.style),
        stroke_width=_stroke_width_for_edge(edge.style),
    )
    arrow_el["points"] = points
    arrow_el["lastCommittedPoint"] = None
    arrow_el["startArrowhead"] = None
    arrow_el["endArrowhead"] = "arrow"
    arrow_el["roundness"] = {"type": 2}

    # Derive fixedPoints from the actual arrow coordinates so they're
    # perfectly consistent with the rendered line (no mismatch).
    start_fp, end_fp = _fixed_points_from_arrow(
        direction,
        (arrow_x, arrow_y),
        (arrow_x + points[-1][0], arrow_y + points[-1][1]),
        node_rects.get(edge.from_id) if node_rects else None,
        node_rects.get(edge.to_id) if node_rects else None,
    )

    from_el = node_elements.get(edge.from_id)
    to_el = node_elements.get(edge.to_id)

    if from_el:
        arrow_el["startBinding"] = {
            "elementId": from_el["id"],
            "focus": 0,
            "gap": 1,
            "fixedPoint": start_fp,
        }
        from_el.setdefault("boundElements", []).append({"id": arrow_id, "type": "arrow"})

    if to_el:
        arrow_el["endBinding"] = {
            "elementId": to_el["id"],
            "focus": 0,
            "gap": 1,
            "fixedPoint": end_fp,
        }
        to_el.setdefault("boundElements", []).append({"id": arrow_id, "type": "arrow"})

    elements: list[dict[str, Any]] = [arrow_el]

    if edge.label:
        font_family = theme.font_family
        lw, lh = _measure_text(edge.label, FONT_SIZE - 2, font_family)
        label_id = _uid()
        mx, my = _path_arc_midpoint(points)
        mid_x = arrow_x + mx - lw / 2
        mid_y = arrow_y + my - lh / 2

        label_el = _base_element(
            "text",
            mid_x,
            mid_y,
            lw,
            lh,
            stroke_color=theme.arrow_label_color,
            roughness=theme.roughness,
            element_id=label_id,
        )
        label_el.update(
            {
                "text": edge.label,
                "fontSize": FONT_SIZE - 2,
                "fontFamily": font_family,
                "textAlign": "center",
                "verticalAlign": "middle",
                "containerId": arrow_id,
                "originalText": edge.label,
                "autoResize": True,
                "lineHeight": _LINE_HEIGHT,
            }
        )
        arrow_el["boundElements"].append({"id": label_id, "type": "text"})
        elements.append(label_el)

    return elements


def _path_arc_midpoint(points: list[list[float]]) -> tuple[float, float]:
    """Return the point at the arc-length midpoint of a polyline path."""
    if len(points) <= 2:
        return (
            (points[0][0] + points[-1][0]) / 2,
            (points[0][1] + points[-1][1]) / 2,
        )
    seg_lengths: list[float] = []
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        seg_lengths.append(math.hypot(dx, dy))
    total = sum(seg_lengths)
    if total == 0:
        return (points[0][0], points[0][1])
    half = total / 2
    accum = 0.0
    for i, sl in enumerate(seg_lengths):
        if accum + sl >= half:
            t = (half - accum) / sl if sl > 0 else 0.0
            mx = points[i][0] + t * (points[i + 1][0] - points[i][0])
            my = points[i][1] + t * (points[i + 1][1] - points[i][1])
            return (mx, my)
        accum += sl
    return (points[-1][0], points[-1][1])


def _clamp_fp(val: float, lo: float = 0.1, hi: float = 0.9) -> float:
    """Clamp a fixedPoint coordinate to [0.1, 0.9] to stay off exact corners."""
    return max(lo, min(val, hi))


def _fixed_points_from_arrow(
    direction: Direction,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    src_pn: PositionedNode | None,
    dst_pn: PositionedNode | None,
) -> tuple[list[float], list[float]]:
    """Derive binding fixedPoints from the actual arrow endpoint coordinates.

    By computing fixedPoints from the same coordinates that _edge_endpoints
    produced, the binding and the rendered line are guaranteed to agree --
    no visual gap between the arrow and the shape.
    """
    if src_pn is None or dst_pn is None:
        match direction:
            case Direction.LEFT_RIGHT:
                return [1.0, 0.5001], [0.0, 0.5001]
            case Direction.RIGHT_LEFT:
                return [0.0, 0.5001], [1.0, 0.5001]
            case Direction.BOTTOM_UP:
                return [0.5001, 0.0], [0.5001, 1.0]
            case _:
                return [0.5001, 1.0], [0.5001, 0.0]

    def _yfp(xy: tuple[float, float], pn: PositionedNode) -> float:
        return _clamp_fp((xy[1] - pn.y) / pn.height) if pn.height > 0 else 0.5

    def _xfp(xy: tuple[float, float], pn: PositionedNode) -> float:
        return _clamp_fp((xy[0] - pn.x) / pn.width) if pn.width > 0 else 0.5

    match direction:
        case Direction.LEFT_RIGHT:
            return [1.0, _yfp(start_xy, src_pn)], [0.0, _yfp(end_xy, dst_pn)]
        case Direction.RIGHT_LEFT:
            return [0.0, _yfp(start_xy, src_pn)], [1.0, _yfp(end_xy, dst_pn)]
        case Direction.BOTTOM_UP:
            return [_xfp(start_xy, src_pn), 0.0], [_xfp(end_xy, dst_pn), 1.0]
        case _:  # TOP_DOWN
            return [_xfp(start_xy, src_pn), 1.0], [_xfp(end_xy, dst_pn), 0.0]


# ---------------------------------------------------------------------------
# Subgraph containers
# ---------------------------------------------------------------------------

def _topo_sort_subgraphs(subgraphs: list[Subgraph]) -> list[str]:
    """Return subgraph IDs in leaf-first order (children before parents).

    This ensures inner containers are computed before outer ones so parent
    bounding boxes can wrap child container bounds.
    """
    sg_ids = {sg.id for sg in subgraphs}
    children_of: dict[str, list[str]] = {sg.id: [] for sg in subgraphs}
    for sg in subgraphs:
        for cid in sg.child_ids:
            if cid in sg_ids:
                children_of[sg.id].append(cid)

    visited: set[str] = set()
    order: list[str] = []

    def _visit(sg_id: str) -> None:
        if sg_id in visited:
            return
        visited.add(sg_id)
        for cid in children_of.get(sg_id, []):
            _visit(cid)
        order.append(sg_id)

    for sg in subgraphs:
        _visit(sg.id)

    return order


SUBGRAPH_PADDING = 30.0
SUBGRAPH_LABEL_HEIGHT = 28.0
SUBGRAPH_LABEL_FONT_SIZE = 14
SUBGRAPH_ICON_SIZE = 32


def _make_subgraph_elements(
    subgraph: Subgraph,
    node_rects: dict[str, PositionedNode],
    theme: Theme,
    files: dict[str, Any] | None = None,
    container_bounds: dict[str, tuple[float, float, float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Build a container rectangle + label + optional icon for a subgraph.

    Computes the bounding box from direct child nodes AND nested child
    container bounds (passed via *container_bounds*), then adds padding.
    If the subgraph has a component_type with a known icon, it is rendered
    in the top-right corner of the container.
    """
    # Collect bounds from direct child nodes
    rects_x: list[float] = []
    rects_y: list[float] = []
    rects_r: list[float] = []
    rects_b: list[float] = []

    for nid in subgraph.node_ids:
        pn = node_rects.get(nid)
        if pn:
            rects_x.append(pn.x)
            rects_y.append(pn.y)
            rects_r.append(pn.x + pn.width)
            rects_b.append(pn.y + pn.height)

    # Include bounds from nested child containers
    if container_bounds:
        for child_sg_id in subgraph.child_ids:
            if child_sg_id in container_bounds:
                cx, cy, cr, cb = container_bounds[child_sg_id]
                rects_x.append(cx)
                rects_y.append(cy)
                rects_r.append(cr)
                rects_b.append(cb)

    if not rects_x:
        return []

    min_x = min(rects_x) - SUBGRAPH_PADDING
    min_y = min(rects_y) - SUBGRAPH_PADDING - SUBGRAPH_LABEL_HEIGHT
    max_x = max(rects_r) + SUBGRAPH_PADDING
    max_y = max(rects_b) + SUBGRAPH_PADDING

    box_w = max_x - min_x
    box_h = max_y - min_y

    group_id = _uid()

    # Container rectangle
    container = _base_element(
        "rectangle",
        min_x,
        min_y,
        box_w,
        box_h,
        stroke_color=theme.group_stroke,
        background_color=theme.group_bg,
        fill_style="solid",
        stroke_width=1,
        stroke_style="dashed" if theme.roughness > 0 else "solid",
        roughness=theme.roughness,
        opacity=60,
    )
    container["roundness"] = {"type": 3}
    container["groupIds"] = [group_id]

    # Label text (top-left inside container)
    font_family = theme.font_family
    lw, lh = _measure_text(subgraph.label, SUBGRAPH_LABEL_FONT_SIZE, font_family)
    label_x = min_x + SUBGRAPH_PADDING * 0.5
    label_y = min_y + 6

    label_el = _base_element(
        "text",
        label_x,
        label_y,
        lw,
        lh,
        stroke_color=theme.group_label_color,
        roughness=theme.roughness,
    )
    label_el.update(
        {
            "text": subgraph.label,
            "fontSize": SUBGRAPH_LABEL_FONT_SIZE,
            "fontFamily": font_family,
            "textAlign": "left",
            "verticalAlign": "top",
            "containerId": None,
            "originalText": subgraph.label,
            "autoResize": True,
            "lineHeight": _LINE_HEIGHT,
        }
    )
    label_el["groupIds"] = [group_id]

    elements: list[dict[str, Any]] = [container, label_el]

    # Icon (top-right corner) — e.g. cloud provider logo on a container
    if subgraph.component_type and files is not None:
        icon_url = get_icon_data_url(subgraph.label, subgraph.component_type)
        if icon_url:
            file_id = _uid()
            files[file_id] = {
                "mimeType": "image/svg+xml",
                "id": file_id,
                "dataURL": icon_url,
                "created": 1,
                "lastRetrieved": 1,
            }
            icon_x = max_x - SUBGRAPH_ICON_SIZE - 8
            icon_y = min_y + 4
            icon_el = _base_element(
                "image",
                icon_x,
                icon_y,
                SUBGRAPH_ICON_SIZE,
                SUBGRAPH_ICON_SIZE,
                stroke_color="transparent",
                roughness=0,
                opacity=70,
            )
            icon_el["status"] = "saved"
            icon_el["fileId"] = file_id
            icon_el["scale"] = [1, 1]
            icon_el["groupIds"] = [group_id]
            elements.append(icon_el)

    # Record bounds so parent containers can wrap around us
    if container_bounds is not None:
        container_bounds[subgraph.id] = (min_x, min_y, max_x, max_y)

    return elements


# ---------------------------------------------------------------------------
# Full file assembly
# ---------------------------------------------------------------------------


def build_excalidraw_file(
    layout: LayoutResult,
    theme_name: ThemeName | str = ThemeName.DEFAULT,
    direction: Direction = Direction.LEFT_RIGHT,
) -> dict[str, Any]:
    """Assemble a complete .excalidraw JSON document from a LayoutResult."""
    theme = get_theme(theme_name)
    all_elements: list[dict[str, Any]] = []
    icon_files: dict[str, Any] = {}

    node_elements: dict[str, dict[str, Any]] = {}
    node_rects: dict[str, PositionedNode] = {}

    for pn in layout.nodes:
        shape_el, extras = _make_shape(pn, theme, files=icon_files)
        node_elements[pn.node.id] = shape_el
        node_rects[pn.node.id] = pn
        all_elements.append(shape_el)
        all_elements.extend(extras)

    # Subgraph containers (rendered behind nodes).
    # Process in topological order: leaf subgraphs first so parent containers
    # can wrap around their computed bounds.
    sg_by_id = {sg.id: sg for sg in layout.subgraphs}
    sg_order = _topo_sort_subgraphs(layout.subgraphs)
    container_bounds: dict[str, tuple[float, float, float, float]] = {}
    subgraph_elements: list[dict[str, Any]] = []
    for sg_id in sg_order:
        sg = sg_by_id[sg_id]
        subgraph_elements.extend(
            _make_subgraph_elements(
                sg, node_rects, theme, files=icon_files,
                container_bounds=container_bounds,
            )
        )
    # Parents are rendered first (behind children) in the element list
    subgraph_elements.reverse()
    all_elements = subgraph_elements + all_elements

    for pe in layout.edges:
        arrow_els = _make_arrow(pe, node_elements, theme, direction, node_rects)
        all_elements.extend(arrow_els)

    metadata = _build_metadata(layout, direction)

    return {
        "type": "excalidraw",
        "version": EXCALIDRAW_VERSION,
        "source": EXCALIDRAW_SOURCE,
        "elements": all_elements,
        "appState": {
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
            "viewBackgroundColor": theme.canvas_background,
            "customData": {
                "arch7_mcp": metadata.model_dump(),
            },
        },
        "files": icon_files,
    }


def _build_metadata(layout: LayoutResult, direction: Direction) -> DiagramMetadata:
    """Build the metadata block for stateful editing."""
    nodes_meta: dict[str, NodeMetadata] = {}
    for pn in layout.nodes:
        nodes_meta[pn.node.id] = NodeMetadata(
            node_id=pn.node.id,
            label=pn.node.label,
            component_type=pn.node.component_type,
            element_ids=[],
        )

    connections_meta: list[ConnectionMetadata] = []
    for pe in layout.edges:
        connections_meta.append(
            ConnectionMetadata(
                from_id=pe.edge.from_id,
                to_id=pe.edge.to_id,
                label=pe.edge.label,
            )
        )

    return DiagramMetadata(
        version=1,
        direction=direction,
        nodes=nodes_meta,
        connections=connections_meta,
    )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def save_excalidraw(data: dict[str, Any], path: str | Path) -> Path:
    """Write the excalidraw JSON to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_excalidraw(path: str | Path) -> dict[str, Any]:
    """Read an excalidraw JSON file from disk."""
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))
