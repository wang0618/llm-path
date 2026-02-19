# Project Requirements

## Overview

LLM Trace is a local proxy that intercepts LLM API requests, logs them to JSONL, and forwards them to the target API.

## Core Requirements

- Proxy HTTP requests to LLM APIs (OpenAI-compatible)
- Support both streaming (SSE) and non-streaming responses
- Save request/response pairs to JSONL format
- Transparent to client applications (just change base_url)

## Technical Requirements

- Async for all HTTP operations
- Thread-safe storage writes
- No external database dependencies
- Configurable target URL and output path

## Future (TODO)

- Visualization tool for request trees
- Request tree construction via message prefix matching
- Web UI for browsing traces
