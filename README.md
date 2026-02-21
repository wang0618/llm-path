# LLM Trace

A lightweight tool for tracing LLM API requests — intercept, record, and visualize your LLM application's behavior.

## Features

- **Transparent Proxy** — Drop-in HTTP proxy that captures all LLM API traffic without code changes
- **Streaming Support** — Full support for SSE (Server-Sent Events) streaming responses
- **Request Visualization** — Interactive web viewer to explore request history as a dependency tree
- **Conversation Branching** — Automatically detects conversation forks (e.g., rewinds) and displays LLM requests as a graph
- **Message Diff View** — Compare messages between consecutive requests to see what changed
- **OpenAI Compatible** — Works with any OpenAI-compatible API

## Installation

```bash
# Clone the repository
git clone https://github.com/wang0618/llm-trace.git
cd llm-trace

# Install Python dependencies
uv sync

# Install viewer dependencies
cd viewer && npm install
```

## Quick Start

### 1. Start the Proxy

```bash
uv run llm-trace proxy --port 8080 --target https://api.openai.com --output ./traces/trace.jsonl
```

### 2. Point Your Client to the Proxy

```python
from openai import OpenAI

# Before
client = OpenAI()

# After — just change the base_url
client = OpenAI(base_url="http://localhost:8080/v1")
```

All requests will be transparently forwarded to the original API and recorded to the trace file.

### 3. Visualize the Traces

```bash
# Preprocess traces for the viewer
uv run llm-trace cook ./traces/trace.jsonl -o ./viewer/public/data.json

# Start the viewer
cd viewer && npm run dev
```

Open http://localhost:5173 to explore your traces.

## How It Works

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Client    │ ──── │  LLM Trace  │ ──── │   LLM API   │
│  (your app) │      │   (proxy)   │      │  (OpenAI)   │
└─────────────┘      └──────┬──────┘      └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ trace.jsonl │
                     └─────────────┘
```

1. Your application sends requests to the local proxy
2. The proxy forwards requests to the target LLM API
3. Responses (including streaming) are passed back to your app
4. Request/response pairs are saved to a JSONL file

### Visualization Model

The viewer displays requests as a **dependency forest**:

- Each node represents one LLM request
- Edges show dependencies — a child request builds upon its parent's messages
- Linear conversations appear as a single chain
- Conversation rewinds or branches create forks
- Unrelated conversations appear as separate trees

## Tech Stack

**Proxy Server**
- Python 3.10+
- Starlette (ASGI framework)
- httpx (async HTTP client)
- uvicorn (ASGI server)

**Viewer**
- React 19
- Vite
- Tailwind CSS v4

## CLI Reference

```bash
# Start proxy server
uv run llm-trace proxy [OPTIONS]
  --port      Port to listen on (default: 8080)
  --output    Output file path (default: ./traces/trace.jsonl)
  --target    Target API URL (default: https://api.openai.com)

# Preprocess traces for visualization
uv run llm-trace cook <input> [OPTIONS]
  -o, --output    Output JSON file (default: ./viewer/public/data.json)
```

## License

MIT
