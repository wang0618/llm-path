# LLM Path

A lightweight tool for tracing LLM API requests — intercept, record, and visualize your LLM application's behavior.

## Features

- **Transparent Proxy** — Drop-in HTTP proxy that captures all LLM API traffic. Works with any OpenAI-compatible API and Anthropic API.
- **Request Visualization** — Interactive web viewer to visualize the requests topology graph and show the context diff between requests.

## Installation

```bash
# Clone the repository
git clone https://github.com/wang0618/llm-path.git
cd llm-path

# Install Python dependencies
uv sync

# Install viewer dependencies
cd viewer && npm install
```

## Quick Start

### 1. Start the Proxy

```bash
uv run llm-path proxy --port 8080 --target https://api.openai.com --output ./traces/trace.jsonl
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
uv run llm-path cook ./traces/trace.jsonl -o ./viewer/public/data.json

# Start the viewer
cd viewer && npm run dev
```

Open http://localhost:5173 to explore your traces.


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
uv run llm-path proxy [OPTIONS]
  --port      Port to listen on (default: 8080)
  --output    Output file path (default: ./traces/trace.jsonl)
  --target    Target API URL (default: https://api.openai.com)

# Preprocess traces for visualization
uv run llm-path cook <input> [OPTIONS]
  -o, --output    Output JSON file (default: ./viewer/public/data.json)
```

## License

MIT
