# arch7

Architecture diagram generator for Excalidraw, exposed as an MCP server.

Fork of [excalidraw-architect-mcp](https://github.com/BV-Venky/excalidraw-architect-mcp) by Bhukya Venkatesh (MIT License).

## What's different

- **Cylinder shapes**: vertical (databases), horizontal flattened (topics/queues)
- **60+ components** with auto-styling: GCP (GKE, Cloud Run, GCS, BigQuery, Pub/Sub, VPC, PSC), Kong, Confluent (Kafka, Schema Registry, ksqlDB), Dynatrace, OpenTelemetry, AI/Agentic (LLM, Agent, MCP, Vector DB, RAG)
- **Smaller diamonds** for agent nodes
- Repackaged as `arch7_mcp`

## Install

```bash
pip install -e .
```

## MCP server (Claude Code)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "arch7": {
      "command": "python",
      "args": ["-m", "arch7_mcp"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `create_diagram` | Structured nodes/connections → .excalidraw |
| `mermaid_to_excalidraw` | Mermaid syntax → .excalidraw |
| `modify_diagram` | Add/remove/update nodes on existing file |
| `get_diagram_info` | Read diagram state for iteration |

## Usage (Python)

```python
from arch7_mcp.core.models import Node, Edge, DiagramGraph, Direction
from arch7_mcp.engine.layout import compute_layout
from arch7_mcp.engine.renderer import build_excalidraw_file, save_excalidraw

nodes = [
    Node(id="gke", label="GKE Cluster", component_type="gke"),
    Node(id="kafka", label="Kafka Topics", component_type="kafka"),
    Node(id="pg", label="PostgreSQL", component_type="postgresql"),
]
edges = [
    Edge(from_id="gke", to_id="kafka"),
    Edge(from_id="kafka", to_id="pg"),
]

graph = DiagramGraph(nodes=nodes, edges=edges, direction=Direction.LEFT_RIGHT)
layout = compute_layout(graph)
doc = build_excalidraw_file(layout)
save_excalidraw(doc, "arch.excalidraw")
```

## License

MIT — see [LICENSE](LICENSE). Original copyright Bhukya Venkatesh.
