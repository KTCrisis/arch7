"""FastMCP server exposing Excalidraw diagram tools.

Four tools:
  1. create_diagram     -- Build a new diagram from structured node/connection data
  2. mermaid_to_excalidraw -- Convert mermaid flowchart syntax to .excalidraw
  3. modify_diagram     -- Iteratively edit an existing diagram
  4. get_diagram_info   -- Read current diagram state for LLM reasoning
"""

from typing import Any

from fastmcp import FastMCP

from arch7_mcp.core.components import detect_component
from arch7_mcp.core.models import (
    AddConnectionOp,
    AddNodeOp,
    DiagramGraph,
    Edge,
    ModifyOperation,
    Node,
    RemoveConnectionOp,
    RemoveNodeOp,
    Subgraph,
    UpdateNodeOp,
)
from arch7_mcp.core.validation import (
    DiagramInputError,
    filter_orphan_connections,
    parse_direction,
    parse_edge_style,
    parse_shape_type,
    validate_node_ids,
)
from arch7_mcp.engine.layout import compute_layout
from arch7_mcp.engine.renderer import build_excalidraw_file, save_excalidraw
from arch7_mcp.parsers.mermaid import parse_mermaid
from arch7_mcp.parsers.state import apply_modifications, get_diagram_summary

mcp = FastMCP(
    "arch7",
    instructions=(
        "Generate Excalidraw architecture diagrams with auto-layout, "
        "cylinder shapes (databases, topics/queues), and component-aware "
        "styling for GCP, Confluent, Kong, Dynatrace. No API keys required."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: create_diagram
# ---------------------------------------------------------------------------


@mcp.tool
def create_diagram(
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    output_path: str,
    direction: str = "LR",
    theme: str = "default",
    subgraphs: list[dict[str, Any]] | None = None,
) -> str:
    """Create a new Excalidraw diagram from structured node and connection data.

    The LLM provides a relationship map - this tool handles layout, styling,
    and rendering. No need to specify coordinates.

    Args:
        nodes: List of nodes. Each dict has:
            - id (str, required): Unique identifier
            - label (str, required): Display text
            - component_type (str, optional): Technology name for auto-styling
              (e.g., "kafka", "postgresql", "redis", "nginx", "kubernetes").
              If omitted, the label is used for auto-detection.
            - shape (str, optional): Override shape - "rectangle", "diamond",
              "ellipse", "circle", "stadium", "parallelogram"
            - color (str, optional): Hex color (e.g. "#6366f1") to override the
              auto-detected background fill. Stroke is darkened automatically.
            - planned (bool, optional): If true, render as a planned/future
              element (dashed stroke + 60% opacity). Default: false.
        connections: List of connections. Each dict has:
            - from_id (str, required): Source node id
            - to_id (str, required): Target node id
            - label (str, optional): Edge label text
            - style (str, optional): "solid", "dashed", "dotted", "thick"
        output_path: File path to save the .excalidraw file (e.g., "./arch.excalidraw")
        direction: Layout direction - "LR" (left-right), "TD" (top-down),
                   "BT" (bottom-up), "RL" (right-left). Default: "LR"
        theme: Color theme - "default", "dark", "colorful", "professional". Default: "default".
                "professional" uses clean lines (no hand-drawn effect) and Helvetica font.
        subgraphs: Optional list of groups (supports nesting). Each dict has:
            - id (str, required): Group identifier
            - label (str, required): Display label for the container
            - node_ids (list[str], required): Direct node ids inside this group
            - child_ids (list[str], optional): IDs of nested child subgroups.
              Parent containers automatically wrap around their children.
            - component_type (str, optional): Technology for container icon
              (e.g., "gke" or "googlecloud" shows a GCP logo top-right).
              Useful for multi-cloud diagrams.

    Returns:
        Summary of the created diagram with file path.
    """
    warnings: list[str] = []

    try:
        validate_node_ids(nodes)
    except DiagramInputError as e:
        return f"Error: {e}"

    graph_nodes = [
        Node(
            id=n["id"],
            label=n.get("label", n["id"]),
            shape=parse_shape_type(n.get("shape"), warnings, context=f"node[{i}]"),
            component_type=n.get("component_type"),
            color=n.get("color"),
            planned=n.get("planned", False),
        )
        for i, n in enumerate(nodes)
    ]

    node_id_set = {n["id"] for n in nodes}
    connections = filter_orphan_connections(connections, node_id_set, warnings)

    graph_edges = [
        Edge(
            from_id=c["from_id"],
            to_id=c["to_id"],
            label=c.get("label"),
            style=parse_edge_style(c.get("style"), warnings, context=f"connection[{i}]"),
        )
        for i, c in enumerate(connections)
    ]

    graph_subgraphs = []
    if subgraphs:
        for sg in subgraphs:
            graph_subgraphs.append(
                Subgraph(
                    id=sg["id"],
                    label=sg.get("label", sg["id"]),
                    node_ids=sg.get("node_ids", []),
                    child_ids=sg.get("child_ids", []),
                    component_type=sg.get("component_type"),
                )
            )

    dir_enum = parse_direction(direction, warnings)
    graph = DiagramGraph(
        nodes=graph_nodes, edges=graph_edges, subgraphs=graph_subgraphs, direction=dir_enum
    )

    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=dir_enum)
    path = save_excalidraw(doc, output_path)

    comp_summary = []
    for n in graph_nodes:
        style = detect_component(n.label, n.component_type)
        if style.category:
            comp_summary.append(f'  - {n.id}: "{n.label}" [{style.category}]')
        else:
            comp_summary.append(f'  - {n.id}: "{n.label}"')

    warn_block = ""
    if warnings:
        warn_block = "Warnings:\n" + "\n".join(f"  - {w}" for w in warnings) + "\n\n"

    return (
        f"Created diagram at: {path}\n"
        f"Nodes ({len(graph_nodes)}):\n" + "\n".join(comp_summary) + "\n"
        f"Connections: {len(graph_edges)}\n"
        f"Direction: {dir_enum.value}\n"
        f"Theme: {theme}\n\n"
        f"{warn_block}"
        f"Open with the VS Code Excalidraw extension or drag into excalidraw.com"
    )


# ---------------------------------------------------------------------------
# Tool 2: mermaid_to_excalidraw
# ---------------------------------------------------------------------------


@mcp.tool
def mermaid_to_excalidraw(
    mermaid_syntax: str,
    output_path: str,
    theme: str = "default",
) -> str:
    """Convert Mermaid flowchart syntax into an Excalidraw diagram.

    Supports the mermaid flowchart subset that AI agents commonly generate:
    - Directions: graph TD, LR, BT, RL
    - Node shapes: [text], {text}, ((text)), ([text])
    - Edge types: -->, ---, -.->  ==>  with |label|
    - Subgraphs: subgraph Title ... end

    Component types are auto-detected from node labels (e.g., a node labeled
    "PostgreSQL DB" automatically gets database styling).

    Args:
        mermaid_syntax: Mermaid flowchart source code.
        output_path: File path to save the .excalidraw file.
        theme: Color theme - "default", "dark", "colorful", "professional". Default: "default".
                "professional" uses clean lines (no hand-drawn effect) and Helvetica font.

    Returns:
        Summary of the converted diagram.
    """
    graph = parse_mermaid(mermaid_syntax)
    layout = compute_layout(graph)
    doc = build_excalidraw_file(layout, theme_name=theme, direction=graph.direction)
    path = save_excalidraw(doc, output_path)

    return (
        f"Converted mermaid to excalidraw at: {path}\n"
        f"Nodes: {len(graph.nodes)}\n"
        f"Connections: {len(graph.edges)}\n"
        f"Subgraphs: {len(graph.subgraphs)}\n"
        f"Direction: {graph.direction.value}\n"
        f"Theme: {theme}\n\n"
        f"Open with the VS Code Excalidraw extension or drag into excalidraw.com"
    )


# ---------------------------------------------------------------------------
# Tool 3: modify_diagram
# ---------------------------------------------------------------------------


@mcp.tool
def modify_diagram(
    file_path: str,
    operations: list[dict[str, Any]],
    theme: str = "default",
) -> str:
    """Modify an existing Excalidraw diagram created by this tool.

    Supports iterative editing: add components, remove nodes, update labels,
    and rewire connections - without recreating the entire diagram.

    IMPORTANT: Call get_diagram_info first to understand the current diagram
    state before making modifications.

    Args:
        file_path: Path to the existing .excalidraw file.
        operations: Ordered list of operations. Each dict has:
            - op: "add_node" | "remove_node" | "update_node" |
                  "add_connection" | "remove_connection"

            For add_node:
              - id (str): New node identifier
              - label (str): Display text
              - component_type (str, optional): Technology for auto-styling
              - shape (str, optional): Shape override
              - color (str, optional): Hex color override
              - planned (bool, optional): Mark as planned/future (dashed + 60% opacity)
              - near (str, optional): Place near this existing node id

            For remove_node:
              - id (str): Node to remove (also removes its connections)

            For update_node:
              - id (str): Node to update
              - label (str, optional): New label
              - component_type (str, optional): New component type
              - color (str, optional): New hex color (pass empty string to clear)
              - planned (bool, optional): Toggle planned state

            For add_connection:
              - from_id (str): Source node id
              - to_id (str): Target node id
              - label (str, optional): Edge label

            For remove_connection:
              - from_id (str): Source node id
              - to_id (str): Target node id

        theme: Color theme for re-rendering. Default: "default"

    Returns:
        Summary of applied modifications.
    """
    warnings: list[str] = []
    parsed_ops: list[ModifyOperation] = []
    for i, op_dict in enumerate(operations):
        op_type = op_dict.get("op", "")
        match op_type:
            case "add_node":
                nid = op_dict.get("id")
                if not isinstance(nid, str) or not nid.strip() or " " in nid:
                    return f"Error: op[{i}] add_node: id must be a non-empty whitespace-free string"
                parsed_ops.append(
                    AddNodeOp(
                        id=nid,
                        label=op_dict.get("label", nid),
                        component_type=op_dict.get("component_type"),
                        shape=parse_shape_type(
                            op_dict.get("shape"), warnings, context=f"op[{i}]"
                        ),
                        color=op_dict.get("color"),
                        planned=op_dict.get("planned", False),
                        near=op_dict.get("near"),
                    )
                )
            case "remove_node":
                parsed_ops.append(RemoveNodeOp(id=op_dict["id"]))
            case "update_node":
                parsed_ops.append(
                    UpdateNodeOp(
                        id=op_dict["id"],
                        label=op_dict.get("label"),
                        component_type=op_dict.get("component_type"),
                        color=op_dict.get("color"),
                        planned=op_dict.get("planned"),
                    )
                )
            case "add_connection":
                parsed_ops.append(
                    AddConnectionOp(
                        from_id=op_dict["from_id"],
                        to_id=op_dict["to_id"],
                        label=op_dict.get("label"),
                    )
                )
            case "remove_connection":
                parsed_ops.append(
                    RemoveConnectionOp(
                        from_id=op_dict["from_id"],
                        to_id=op_dict["to_id"],
                    )
                )
            case _:
                return f"Error: Unknown operation type '{op_type}'"

    result = apply_modifications(file_path, parsed_ops, theme=theme)
    if warnings:
        result += "\n\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)
    return result


# ---------------------------------------------------------------------------
# Tool 4: get_diagram_info
# ---------------------------------------------------------------------------


@mcp.tool
def get_diagram_info(file_path: str) -> str:
    """Get a structured summary of an existing Excalidraw diagram.

    Call this BEFORE modify_diagram to understand what nodes and connections
    currently exist. The summary includes node ids, labels, component types,
    and the full connection topology.

    Args:
        file_path: Path to the .excalidraw file.

    Returns:
        Human-readable summary of all nodes and connections.
    """
    return get_diagram_summary(file_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the MCP server over stdio."""
    mcp.run()
