# LLM Path

A tool for tracing LLM requests - intercepts API calls and saves them for debugging and analysis.

## Quick Reference

```bash
# Start proxy server (--output and --target are required)
llm-path proxy --port 8080 --target https://api.openai.com --output ./traces/trace.jsonl

# Preprocess traces for visualization
llm-path cook ./traces/trace.jsonl -o ./viewer/public/data.json

# Visualize traces (starts web server, auto-cooks if needed)
llm-path viewer trace.jsonl

# Install Python dependencies
uv sync

# Lint/format Python
uv run ruff check llm_path/
uv run ruff format llm_path/

# Run viewer dev mode (React)
cd viewer && npm install && npm run dev

# Load data from custom path in viewer
open http://localhost:port/?data=path/to/other.json
```

## Directory Structure

```
llm-path/
├── llm_path/           # Main package
│   ├── cli.py           # CLI entry point (subcommands: proxy, cook, viewer)
│   ├── cook/            # Trace preprocessing package
│   │   ├── __init__.py       # Public API: cook_traces(), TraceCooker
│   │   ├── models.py         # CookedMessage, CookedTool, CookedRequest, CookedOutput
│   │   ├── deduplicator.py   # MessageDeduplicator, ToolDeduplicator
│   │   ├── dependency.py     # DependencyAnalyzer (Levenshtein + tool matching)
│   │   ├── base.py           # BaseProvider abstract class
│   │   ├── cooker.py         # TraceCooker coordinator
│   │   └── providers/        # API format providers
│   │       ├── __init__.py   # Provider registry
│   │       ├── openai.py     # OpenAI format (+ SSE parsing)
│   │       ├── claude.py     # Claude format (+ SSE parsing)
│   │       └── gemini.py     # Gemini format
│   ├── proxy.py         # Proxy server (Starlette + httpx)
│   ├── storage.py       # JSONL append-only storage
│   ├── viewer.py        # Viewer server (serves React app + data)
│   └── models.py        # TraceRecord dataclass
├── viewer/              # React trace viewer (Vite + Tailwind)
│   ├── src/components/  # React components (detail/, sidebar/, diff/, layout/)
│   ├── src/hooks/       # Custom hooks (useTraceData, useDiff, useTheme)
│   ├── src/utils/       # Utilities (diff.ts, treeLayout.ts)
│   └── public/data.json # Cooked trace data (output of `cook`)
├── docs/                # Design documentation
├── traces/              # Default output directory
└── pyproject.toml       # Project config
```

## Tech Stack

- **Framework**: Starlette (ASGI)
- **HTTP Client**: httpx (async, streaming)
- **Server**: uvicorn
- **Storage**: JSONL (append-only, no database)
- **Python**: 3.10+
- **Viewer**: React 19 + Vite + Tailwind CSS v4

## Key Concepts

### Proxy Flow

1. Client sends request to `localhost:8080/v1/...`
2. Proxy forwards to target API (specified via `--target`)
3. Response is streamed back (if SSE) or returned whole
4. Request/response pair saved to JSONL

### Streaming (SSE)

- Chunks forwarded in real-time to client
- Content deltas collected and reassembled
- Complete response saved after stream ends

### Storage Format

Each line in JSONL:
```json
{"id": "uuid", "timestamp": "ISO", "request": {...}, "response": {...}, "duration_ms": 1200}
```

### Cook (Preprocessing)

The `cook` command transforms raw JSONL traces into visualization-ready JSON:

- **Message deduplication**: Same messages get reused across requests via hash-based IDs
- **Tool deduplication**: Tool definitions are deduplicated by (name, description, parameters)
- **Role mapping**:
  - `assistant` with tool_calls → `tool_use`
  - `tool` → `tool_result`
  - Claude thinking blocks → separate `thinking` messages
  - Gemini `model` → `assistant`
  - Gemini `function_call` → `tool_use`
  - Gemini `function_response` → `tool_result`
- **Response messages**: Each request has `response_messages` (array) to support multiple response parts (e.g., thinking + assistant)
- **Request dependency analysis**: Builds a dependency forest (not linear chain) by:
  - Using Levenshtein distance for parent detection
  - Filtering by model (no cross-model dependencies)
  - Applying tool difference penalties to match scores
  - Creating new roots when match score is below threshold

Output structure:
```json
{"messages": [...], "tools": [...], "requests": [...]}
```

See `docs/request-dependency.md` for algorithm details.

### Cook Package Architecture

The cook module uses a provider-based architecture for extensibility:

- **Outer modules** (`cooker.py`, `deduplicator.py`, `dependency.py`) only work with standardized data classes (`CookedMessage`, `CookedRequest`, etc.)
- **Providers** (`providers/openai.py`, `providers/claude.py`, `providers/gemini.py`) encapsulate all format-specific logic including SSE parsing
- **Supported formats**: OpenAI, Claude (Anthropic), Gemini (Google) - auto-detected or specified via `--format` flag
- **Adding a new provider**: Create `providers/newapi.py` implementing `BaseProvider`, register in `providers/__init__.py`

## Viewer Features

- **Request graph**: Visual tree/forest of request dependencies in sidebar. See `docs/request-graph-implementation.md` for implementation details.
- **Message diff view**: Compare messages between consecutive requests
- **Dark/light theme**: Toggle via ThemeProvider
- **Collapsible content**: Messages and tool descriptions collapse for readability

### Visualization Model

The viewer displays requests as a **dependency forest**:

- Each node represents one LLM request
- Edges show dependencies — a child request builds upon its parent's messages
- Linear conversations appear as a single chain
- Conversation rewinds or branches create forks
- Unrelated conversations appear as separate trees

## Conventions

- Type hints on all functions
- Async for HTTP operations
- Dataclasses for data models
- Relative imports within package (`from .models import ...`)

## What NOT to Do

- NEVER edit .env or credentials
- NEVER commit trace files with sensitive data
- NEVER add eslint-disable style comments - fix the issue
- NEVER create abstractions that weren't requested

## Testing

TODO: Set up pytest

