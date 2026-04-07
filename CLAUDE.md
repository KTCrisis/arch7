# CLAUDE.md — arch7

## What it is

Architecture diagram generator for Excalidraw, exposed as an MCP server.
Fork of [excalidraw-architect-mcp](https://github.com/BV-Venky/excalidraw-architect-mcp) v0.2.3 (MIT).

## Quick commands

```bash
pip install -e .                    # editable install
python -m arch7_mcp                 # run MCP server (stdio)
arch7                               # same, via entry point
```

## Structure

```
arch7_mcp/
├── core/
│   ├── components.py    # 60+ component registry (GCP, Kong, Confluent, Dynatrace, AI...)
│   ├── models.py        # Pydantic models, ShapeType (incl. CYLINDER_V, CYLINDER_H)
│   └── themes.py        # default, dark, colorful
├── engine/
│   ├── layout.py        # Sugiyama auto-layout (grandalf), node sizing
│   └── renderer.py      # Excalidraw JSON builder, cylinder shapes
├── parsers/
│   ├── mermaid.py       # Mermaid → DiagramGraph
│   └── state.py         # Stateful modifications
└── server.py            # FastMCP server, 4 tools
```

## MCP Tools

| Tool | Input | Output |
|------|-------|--------|
| `create_diagram` | nodes[] + connections[] + output_path | .excalidraw file |
| `mermaid_to_excalidraw` | mermaid syntax + output_path | .excalidraw file |
| `modify_diagram` | file_path + operations[] | modified .excalidraw |
| `get_diagram_info` | file_path | text summary |

## Component types (component_type field)

Use these for auto-styling — shape + color + badge applied automatically:

- **GCP**: `gke`, `cloud run`, `cloud function`, `gcs`, `bigquery`, `cloud sql`, `pub/sub`, `vpc`, `psc`, `cloud armor`
- **Kong**: `kong`, `kong konnect`
- **Confluent**: `kafka`, `topic`, `confluent`, `schema registry`, `ksqldb`, `connect`
- **Databases**: `postgresql`, `mysql`, `mongodb`, `dynamodb`, `clickhouse`, `cassandra`, `sqlite`, `elasticsearch` → CYLINDER_V
- **Queues**: `kafka`, `rabbitmq`, `sqs`, `nats`, `pulsar`, `pub/sub` → CYLINDER_H (flattened)
- **AI/Agentic**: `llm`, `agent`, `crewai`, `langchain`, `mcp`, `vector`, `rag`
- **Monitoring**: `dynatrace`, `opentelemetry`, `prometheus`, `grafana`, `datadog`
- **Infra**: `nginx`, `haproxy`, `envoy`, `traefik`, `redis`, `cloudflare`, `docker`, `kubernetes`

## Shapes

| ShapeType | Rendered as | Used for |
|-----------|-------------|----------|
| RECTANGLE | Rectangle | Services, APIs, infra |
| DIAMOND | Diamond (reduced 85%) | Agents |
| ELLIPSE | Ellipse | LLMs, users |
| CYLINDER_V | Vertical cylinder (grouped lines + ellipse) | Databases |
| CYLINDER_H | Horizontal flattened cylinder | Topics, queues |

## Diagram design guide

### Graph topology

- Keep it **tree-like** — aim for N-1 to N+2 edges for N nodes
- No node should have 5+ incoming edges — remove or group
- Hub fan-out: 3–5, not 6+
- Balance layers: 1–4 nodes per column

### Node guidelines

| Diagram type | Ideal count |
|---|---|
| High-level architecture | 6–15 |
| Detailed service flow | 10–25 |
| Deep-dive | 15–30 |

### Edge guidelines

- `solid` = primary data flow
- `dashed` = async, optional, metadata
- `dotted` = monitoring, observability
- `thick` = critical path
- Labels: **max 4 words**

### Direction

- `LR` (default): architecture, data pipelines
- `TD`: org charts, hierarchies, decision trees

### Anti-patterns

- Every import as an edge → show primary data flow only
- Shared node with 4+ incoming → remove or group
- Long edge labels → excessive spacing
- 30+ nodes → split into multiple diagrams
- Multiple fork-merges → linearize or split

## Don't

- Don't modify upstream Excalidraw format assumptions (version, appState structure)
- Don't add component_type aliases that conflict (check `_COMPONENTS` dict first)
- Don't generate coordinates manually — always use `compute_layout()`
