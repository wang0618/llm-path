# Data Format Specification

This document describes the input formats supported by the `cook` command and the output format it produces.

## Input Formats

The `cook` command supports three API formats: **OpenAI**, **Claude**, and **Gemini**. Format is auto-detected per record, or can be specified via `--format` flag.

### OpenAI Format

#### Request Structure

```json
{
  "id": "uuid",
  "timestamp": "2026-02-20T10:00:00Z",
  "duration_ms": 1200,
  "request": {
    "model": "gpt-4",
    "messages": [...],
    "tools": [...]
  },
  "response": {
    "choices": [...]
  },
  "error": null
}
```

#### Message Types

**System Message**
```json
{"role": "system", "content": "You are a helpful assistant."}
```

**User Message (text)**
```json
{"role": "user", "content": "Hello, how are you?"}
```

**User Message (with images)**
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What's in this image?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  ]
}
```

**Assistant Message (text only)**
```json
{"role": "assistant", "content": "I'm doing well, thank you!"}
```

**Assistant Message (with tool calls)**
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"Tokyo\"}"
      }
    }
  ]
}
```

**Tool Result Message**
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "Sunny, 22°C"
}
```

#### Tool Definition

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {"type": "string"}
      },
      "required": ["location"]
    }
  }
}
```

#### Response Structure

**Non-streaming:**
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello!",
        "tool_calls": null
      }
    }
  ]
}
```

**Streaming (raw SSE lines):**
```json
{
  "stream": true,
  "sse_lines": [
    "data: {\"id\":\"chatcmpl-xxx\",\"model\":\"gpt-4\",\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}",
    "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}",
    "data: {\"choices\":[{\"delta\":{\"content\":\"!\"}}]}",
    "data: [DONE]"
  ]
}
```

---

### Claude Format

#### Request Structure

```json
{
  "id": "uuid",
  "timestamp": "2026-02-20T10:00:00Z",
  "duration_ms": 1200,
  "request": {
    "model": "claude-sonnet-4-20250514",
    "system": [...],
    "messages": [...],
    "tools": [...]
  },
  "response": {
    "content": [...]
  },
  "error": null
}
```

#### System Field

Claude uses a separate `system` field (array of content blocks) instead of a system message:

```json
{
  "system": [
    {"type": "text", "text": "You are a helpful assistant."},
    {"type": "text", "text": "Always be concise."}
  ]
}
```

#### Message Types

**User Message (text)**
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Hello, how are you?"}
  ]
}
```

Or simple string form:
```json
{"role": "user", "content": "Hello, how are you?"}
```

**User Message (with images)**
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What's in this image?"},
    {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": "image/png",
        "data": "..."
      }
    }
  ]
}
```

**User Message (with tool result)**
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "call_abc123",
      "content": "Sunny, 22°C",
      "is_error": false
    }
  ]
}
```

**Assistant Message (text only)**
```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "I'm doing well, thank you!"}
  ]
}
```

**Assistant Message (with thinking)**
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "thinking",
      "thinking": "The user is asking about my wellbeing...",
      "signature": ""
    },
    {"type": "text", "text": "I'm doing well, thank you!"}
  ]
}
```

**Assistant Message (with tool use)**
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "thinking",
      "thinking": "I need to check the weather...",
      "signature": ""
    },
    {
      "type": "tool_use",
      "id": "call_abc123",
      "name": "get_weather",
      "input": {"location": "Tokyo"}
    }
  ]
}
```

#### Tool Definition

```json
{
  "name": "get_weather",
  "description": "Get current weather for a location",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"]
  }
}
```

#### Response Structure

```json
{
  "content": [
    {"type": "text", "text": "Hello!"}
  ]
}
```

Or with tool use:
```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": "...",
      "signature": ""
    },
    {
      "type": "tool_use",
      "id": "call_xyz",
      "name": "Bash",
      "input": {"command": "ls"}
    }
  ]
}
```

**Streaming (raw SSE lines):**
```json
{
  "stream": true,
  "sse_lines": [
    "event: message_start",
    "data: {\"type\":\"message_start\",\"message\":{\"id\":\"msg_xxx\",\"model\":\"claude-sonnet-4-20250514\"}}",
    "event: content_block_start",
    "data: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"text\",\"text\":\"\"}}",
    "event: content_block_delta",
    "data: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"Hello!\"}}",
    "event: content_block_stop",
    "data: {\"type\":\"content_block_stop\",\"index\":0}",
    "event: message_delta",
    "data: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"end_turn\"}}",
    "event: message_stop",
    "data: {\"type\":\"message_stop\"}"
  ]
}
```

---

### Gemini Format

Both camelCase and snake_case are supported for fields.

#### Request Structure

```json
{
  "id": "uuid",
  "timestamp": "2026-02-20T10:00:00Z",
  "duration_ms": 1200,
  "request": {
    "contents": [...],
    "systemInstruction": {...},
    "tools": [...]
  },
  "response": {
    "candidates": [...],
    "modelVersion": "gemini-2.0-flash"
  },
  "error": null
}
```

#### System Instruction

Gemini uses a separate system instruction field with `parts` array.

```json
{
  "systemInstruction": {
    "parts": [
      {"text": "You are a helpful assistant."}
    ]
  }
}
```

#### Message Types (Contents)

Gemini uses `contents` instead of `messages`, and `model` instead of `assistant` for the role.

**User Message**
```json
{
  "role": "user",
  "parts": [
    {"text": "Hello, how are you?"}
  ]
}
```

**Model Message (text only)**
```json
{
  "role": "model",
  "parts": [
    {"text": "I'm doing well, thank you!"}
  ]
}
```

**Model Message (with function call)**
```json
{
  "role": "model",
  "parts": [
    {"text": "Let me check the weather for you."},
    {
      "function_call": {
        "name": "get_weather",
        "args": {"location": "Tokyo"}
      }
    }
  ]
}
```

**Function Response (tool result)**

Function responses have no role (or role is `None`):
```json
{
  "parts": [
    {
      "function_response": {
        "name": "get_weather",
        "response": {
          "content": "Sunny, 22°C"
        }
      }
    }
  ]
}
```

#### Tool Definition

Gemini wraps tool definitions in `function_declarations`:

```json
{
  "tools": [
    {
      "function_declarations": [
        {
          "name": "get_weather",
          "description": "Get current weather for a location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": {"type": "string"}
            },
            "required": ["location"]
          }
        }
      ]
    }
  ]
}
```

#### Response Structure

```json
{
  "candidates": [
    {
      "content": {
        "role": "model",
        "parts": [
          {"text": "Hello!"}
        ]
      },
      "finishReason": "STOP"
    }
  ],
  "modelVersion": "gemini-2.0-flash"
}
```

With function call:
```json
{
  "candidates": [
    {
      "content": {
        "role": "model",
        "parts": [
          {
            "function_call": {
              "name": "get_weather",
              "args": {"location": "Tokyo"}
            },
            "thoughtSignature": "..."
          }
        ]
      }
    }
  ]
}
```

Note: `thoughtSignature` indicates thinking mode was used, but the actual thinking content is not exposed in Gemini's API.

---

## Output Format (Cooked)

The `cook` command transforms traces into a deduplicated, visualization-ready format:

```json
{
  "messages": [...],
  "tools": [...],
  "requests": [...]
}
```

### CookedMessage

```json
{
  "id": "m0",
  "role": "system" | "user" | "assistant" | "tool_use" | "tool_result" | "thinking",
  "content": "string",
  "tool_calls": [{"name": "...", "arguments": {...}, "id": "call_xxx"}] | null,
  "tool_use_id": "call_xxx" | null,
  "is_error": true | false | null
}
```

**Field Notes:**
- `tool_calls[].id`: Tool use ID from the API (present for Claude and OpenAI tool calls)
- `tool_use_id`: For `tool_result` messages, references the `tool_use` it responds to
- `is_error`: For `tool_result` messages, indicates whether the tool execution failed

### CookedTool

```json
{
  "id": "t0",
  "name": "get_weather",
  "description": "Get current weather",
  "parameters": {...}
}
```

### CookedRequest

```json
{
  "id": "uuid",
  "parent_id": "uuid" | null,
  "timestamp": 1708419600000,
  "request_messages": ["m0", "m1", "m2"],
  "response_messages": ["m3"],
  "model": "gpt-4",
  "tools": ["t0", "t1"],
  "duration_ms": 1200
}
```

Note: `response_messages` is an array to support multiple response parts. Text content and tool calls are split into separate messages (consistent with request handling), enabling accurate diff calculation between consecutive requests. Example parts: thinking message, text message, tool_use message.

---

## Transformation Rules

### Format Detection

A record is detected as **Gemini** format if any of these conditions are met:
1. `request.contents` exists (instead of `messages`)
2. `request.system_instruction` or `request.systemInstruction` exists
3. Tools have `function_declarations` array
4. Response has `candidates` with `content.parts` structure
5. Response has `modelVersion` field

A record is detected as **Claude** format if any of these conditions are met:
1. **Streaming response**: SSE lines contain events with `type` in (`message_start`, `content_block_start`, `content_block_delta`, `message_delta`, `message_stop`)
2. `request.system` is a list
3. First tool has `input_schema` field
4. Messages contain content blocks with `type` in (`tool_use`, `tool_result`, `thinking`)

Otherwise, it's treated as **OpenAI** format.

### Role Mapping

| Source | Condition | Output Role |
|--------|-----------|-------------|
| OpenAI `system` | - | `system` |
| OpenAI `user` | - | `user` |
| OpenAI `assistant` | no tool_calls | `assistant` |
| OpenAI `assistant` | has tool_calls | `tool_use` |
| OpenAI `tool` | - | `tool_result` |
| Claude `system` field | - | `system` |
| Claude `user` | text blocks only | `user` |
| Claude `user` | has tool_result blocks | `tool_result` (separate messages) |
| Claude `assistant` | text blocks only | `assistant` |
| Claude `assistant` | has tool_use blocks | `tool_use` |
| Claude `assistant` | thinking blocks | `thinking` (separate messages) |
| Gemini `systemInstruction` / `system_instruction` | - | `system` |
| Gemini `user` | - | `user` |
| Gemini `model` | text parts only | `assistant` |
| Gemini `model` | has function_call | `tool_use` |
| Gemini (no role) | has function_response | `tool_result` |

### Content Block Processing (Claude)

| Block Type | Processing |
|------------|------------|
| `text` | Each block becomes a separate message |
| `thinking` | Separate message with `thinking` role |
| `tool_use` | Collected into `tool_calls` array: `{name, arguments: input}` |
| `tool_result` | Separate message with `tool_result` role |
| `image` | Placeholder `[image]` |

### Parts Processing (Gemini)

| Part Type | Processing |
|-----------|------------|
| `text` | Concatenated into message content |
| `function_call` / `functionCall` | Collected into `tool_calls` array: `{name, arguments: args}` |
| `function_response` / `functionResponse` | Separate message with `tool_result` role |
| `thoughtSignature` | Ignored (no content exposed) |

### Tool Definition Normalization

| Source | Output |
|--------|--------|
| OpenAI `function.name` | `name` |
| OpenAI `function.description` | `description` |
| OpenAI `function.parameters` | `parameters` |
| Claude `name` | `name` |
| Claude `description` | `description` |
| Claude `input_schema` | `parameters` |
| Gemini `function_declarations[].name` | `name` |
| Gemini `function_declarations[].description` | `description` |
| Gemini `function_declarations[].parameters` | `parameters` |

### Tool Calls Normalization

| Source | Output |
|--------|--------|
| OpenAI `function.name` | `name` |
| OpenAI `function.arguments` (JSON string) | `arguments` (parsed to object) |
| OpenAI `id` | `id` |
| Claude `name` | `name` |
| Claude `input` | `arguments` |
| Claude `id` | `id` |
| Gemini `function_call.name` | `name` |
| Gemini `function_call.args` | `arguments` |

### Tool Result Normalization

| Source | Output |
|--------|--------|
| OpenAI `tool_call_id` | `tool_use_id` |
| Claude `tool_use_id` | `tool_use_id` |
| Claude `is_error` | `is_error` |
| Gemini `function_response.name` | `tool_use_id` (uses function name as reference) |
| Gemini `function_response.response.content` | `content` |

### Deduplication

Messages and tools are deduplicated using SHA-256 hash (first 16 chars):

- **Message hash**: `hash(role, content, tool_calls, tool_use_id, is_error)`
- **Tool hash**: `hash(name, description, parameters)`

Identical messages/tools across requests share the same ID.

### Thinking Block Handling

Thinking blocks are extracted as separate messages with role `thinking`. This enables:
- Better visualization with distinct styling
- Filtering/collapsing thinking content independently
- Multiple response messages per request (e.g., `["thinking_msg_id", "assistant_msg_id"]`)

### Streaming Response (SSE) Parsing

Streaming responses are stored as raw SSE lines and parsed during the `cook` phase.

#### OpenAI SSE Events

| Event Data Field | Processing |
|------------------|------------|
| `choices[0].delta.content` | Concatenated to form final text content |
| `choices[0].delta.tool_calls` | Accumulated by index, arguments concatenated |
| `id`, `model` | Extracted from first chunk |

#### Claude SSE Events

| Event Type | Processing |
|------------|------------|
| `message_start` | Extract `id` and `model` from `message` field |
| `content_block_start` | Initialize block by index with `type`, `name` |
| `content_block_delta` | Accumulate `text_delta.text`, `thinking_delta.thinking`, or `input_json_delta.partial_json` |
| `message_delta` | Extract `stop_reason` |

Claude content blocks are reconstructed and converted to the standard response format before further processing.

---

## Examples

### OpenAI Request → Cooked

**Input:**
```json
{
  "request": {
    "messages": [
      {"role": "system", "content": "Be helpful"},
      {"role": "user", "content": "What's 2+2?"},
      {"role": "assistant", "content": null, "tool_calls": [
        {"type": "function", "function": {"name": "calc", "arguments": "{\"expr\":\"2+2\"}"}}
      ]},
      {"role": "tool", "content": "4"}
    ]
  }
}
```

**Output Messages:**
```json
[
  {"id": "m0", "role": "system", "content": "Be helpful", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m1", "role": "user", "content": "What's 2+2?", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m2", "role": "tool_use", "content": "", "tool_calls": [{"name": "calc", "arguments": {"expr": "2+2"}, "id": "call_abc"}], "tool_use_id": null, "is_error": null},
  {"id": "m3", "role": "tool_result", "content": "4", "tool_calls": null, "tool_use_id": "call_abc", "is_error": false}
]
```

### Claude Request → Cooked

**Input:**
```json
{
  "request": {
    "system": [{"type": "text", "text": "Be helpful"}],
    "messages": [
      {"role": "user", "content": [{"type": "text", "text": "What's 2+2?"}]},
      {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "Simple math question"},
        {"type": "tool_use", "id": "call_1", "name": "calc", "input": {"expr": "2+2"}}
      ]},
      {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "4"}
      ]}
    ]
  }
}
```

**Output Messages:**
```json
[
  {"id": "m0", "role": "system", "content": "Be helpful", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m1", "role": "user", "content": "What's 2+2?", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m2", "role": "thinking", "content": "Simple math question", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m3", "role": "tool_use", "content": "", "tool_calls": [{"name": "calc", "arguments": {"expr": "2+2"}, "id": "call_1"}], "tool_use_id": null, "is_error": null},
  {"id": "m4", "role": "tool_result", "content": "4", "tool_calls": null, "tool_use_id": "call_1", "is_error": false}
]
```

Note: Thinking blocks become separate messages (m2) instead of being merged into tool_use content.

### Gemini Request → Cooked

**Input:**
```json
{
  "request": {
    "systemInstruction": {
      "parts": [{"text": "Be helpful"}]
    },
    "contents": [
      {"role": "user", "parts": [{"text": "What's 2+2?"}]},
      {"role": "model", "parts": [
        {"function_call": {"name": "calc", "args": {"expr": "2+2"}}}
      ]},
      {"parts": [
        {"function_response": {"name": "calc", "response": {"content": "4"}}}
      ]}
    ]
  }
}
```

**Output Messages:**
```json
[
  {"id": "m0", "role": "system", "content": "Be helpful", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m1", "role": "user", "content": "What's 2+2?", "tool_calls": null, "tool_use_id": null, "is_error": null},
  {"id": "m2", "role": "tool_use", "content": "", "tool_calls": [{"name": "calc", "arguments": {"expr": "2+2"}}], "tool_use_id": null, "is_error": null},
  {"id": "m3", "role": "tool_result", "content": "4", "tool_calls": null, "tool_use_id": "calc", "is_error": null}
]
```

Note: Gemini uses function name as the `tool_use_id` reference since it doesn't provide explicit call IDs.
