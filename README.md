 <h1 align="center">LLM Path</h1>
<p align="center">
    <em>A lightweight tool for tracing LLM API requests.</em>
</p>


<p align="center">
  <img src="./docs/images/screenshot.jpeg" alt="Screenshot" width="800"/>
</p>

<div align="center">

Trace demo: [nanobot](https://wang0618.github.io/llm-path/?data=nanobot.json)[^nanobot], [claude code](https://wang0618.github.io/llm-path/?data=claude-code.json), [deep research](https://wang0618.github.io/llm-path/?data=adk-deepresearch.json)[^deepresearch]

</div>

[^nanobot]: [nanobot](https://github.com/HKUDS/nanobot) is a lightweight OpenClaw implementation in Python.

[^deepresearch]: The deep research agent is from the Google ADK demo, see [deepresearch](https://github.com/google/adk-samples/blob/main/python/agents/deep-search/)


## Features

- **Transparent Proxy** — Drop-in HTTP proxy that captures all LLM API traffic. Works with OpenAI, Anthropic (Claude), and Google (Gemini) APIs.
- **Request Visualization** — Interactive web viewer to visualize the request topology graph and show the context diff between requests.

## Installation

```bash
pip install llm-path
```

## Quick Start

### 1. Start the Proxy

```bash
llm-path proxy --port 8080 --target https://api.openai.com --output trace.jsonl
```

Replace the `--target` host in the command above with your LLM provider's API host.

### 2. Point Your Client to the Proxy

```diff
from openai import OpenAI

- client = OpenAI()
+ client = OpenAI(base_url="http://localhost:8080/v1")
```

All requests will be transparently forwarded to your LLM provider and recorded to the trace file.

### 3. Visualize the Traces

```bash
llm-path viewer trace.jsonl
```

## Proxy for More Providers

<details>
<summary>Google Agent Development Kit (ADK)</summary>

Start the proxy:
```bash
llm-path proxy --port 8080 --target https://generativelanguage.googleapis.com --output adk.jsonl
```

Set the environment variable for your ADK application:
```bash
GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:8080
```

</details>

## CLI Reference

```bash
# Start proxy server
llm-path proxy [OPTIONS]
  --port      Port to listen on (default: 8080)
  --output    Output JSONL file path (required)
  --target    LLM Provider API URL (required)

# Visualize traces
llm-path viewer <input> [OPTIONS]
  --port      Port to listen on (default: 8765)
  --host      Host to bind to (default: 127.0.0.1)
```

## Development Guide

```bash
git clone https://github.com/wang0618/llm-path.git
cd llm-path
uv sync

uv run llm-path proxy --port 8080 --target https://api.openai.com --output trace.jsonl &
uv run llm-path cook trace.jsonl -o ./viewer/public/data.json

cd viewer
npm install
npm run dev
```

## License

MIT
