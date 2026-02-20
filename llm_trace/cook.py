"""Preprocessing module to convert JSONL traces to visualization-ready JSON."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ApiFormat = Literal["auto", "openai", "claude"]


@dataclass
class CookedMessage:
    """Deduplicated message with stable ID."""

    id: str
    role: str  # "system" | "user" | "tool_use" | "tool_result" | "assistant" | "thinking"
    content: str
    tool_calls: list[dict] | None = None


@dataclass
class CookedTool:
    """Deduplicated tool definition with stable ID."""

    id: str
    name: str
    description: str
    parameters: dict


@dataclass
class CookedRequest:
    """A single request/response pair with references to messages and tools."""

    id: str
    parent_id: str | None
    timestamp: int  # Unix milliseconds
    request_messages: list[str]  # Message IDs
    response_messages: list[str]  # Message IDs
    model: str
    tools: list[str]  # Tool IDs
    duration_ms: int


@dataclass
class CookedOutput:
    """Final output structure for visualization."""

    messages: list[CookedMessage] = field(default_factory=list)
    tools: list[CookedTool] = field(default_factory=list)
    requests: list[CookedRequest] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "messages": [asdict(m) for m in self.messages],
            "tools": [asdict(t) for t in self.tools],
            "requests": [asdict(r) for r in self.requests],
        }


def _compute_message_hash(role: str, content: str, tool_calls: list[dict] | None) -> str:
    """Compute stable hash for message deduplication."""
    data = {
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
    }
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def _compute_tool_hash(name: str, description: str, parameters: dict) -> str:
    """Compute stable hash for tool deduplication."""
    data = {
        "name": name,
        "description": description,
        "parameters": parameters,
    }
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def _map_role(role: str, tool_calls: list[dict] | None) -> str:
    """Map original role to visualization role."""
    if role == "assistant" and tool_calls:
        return "tool_use"
    if role == "tool":
        return "tool_result"
    return role


def _parse_openai_sse(sse_lines: list[str]) -> dict:
    """Parse OpenAI SSE lines into a response dict.

    OpenAI format:
        data: {"id": "xxx", "model": "gpt-4", "choices": [{"delta": {"content": "Hi"}}]}
        data: [DONE]
    """
    response_id = None
    model = None
    content_parts = []
    tool_calls: dict[int, dict] = {}  # index -> {name, arguments}

    for line in sse_lines:
        if not line.startswith("data: "):
            continue

        data = line[6:]
        if data == "[DONE]":
            continue

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        # Extract metadata
        if response_id is None:
            response_id = chunk.get("id")
        if model is None:
            model = chunk.get("model")

        # Extract content delta
        choices = chunk.get("choices", [])
        if not choices:
            continue

        delta = choices[0].get("delta", {})

        # Text content
        content = delta.get("content")
        if content:
            content_parts.append(content)

        # Tool calls
        delta_tool_calls = delta.get("tool_calls", [])
        for tc in delta_tool_calls:
            idx = tc.get("index", 0)
            if idx not in tool_calls:
                tool_calls[idx] = {"id": "", "name": "", "arguments": ""}

            if "id" in tc:
                tool_calls[idx]["id"] = tc["id"]
            if "function" in tc:
                func = tc["function"]
                if "name" in func:
                    tool_calls[idx]["name"] = func["name"]
                if "arguments" in func:
                    tool_calls[idx]["arguments"] += func["arguments"]

    # Build response in OpenAI format
    message: dict = {
        "role": "assistant",
        "content": "".join(content_parts),
    }

    if tool_calls:
        message["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]},
            }
            for tc in sorted(tool_calls.values(), key=lambda x: x.get("id", ""))
        ]

    return {
        "id": response_id,
        "model": model,
        "choices": [{"message": message}],
    }


def _parse_claude_sse(sse_lines: list[str]) -> dict:
    """Parse Claude SSE lines into a response dict.

    Claude format:
        event: message_start
        data: {"type": "message_start", "message": {"id": "xxx", "model": "..."}}

        event: content_block_delta
        data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}

        event: message_stop
        data: {"type": "message_stop"}
    """
    response_id = None
    model = None
    content_blocks: dict[int, dict] = {}  # index -> {type, text/name/input}
    stop_reason = None

    for line in sse_lines:
        if not line.startswith("data: "):
            continue

        data = line[6:]
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        event_type = chunk.get("type", "")

        if event_type == "message_start":
            message = chunk.get("message", {})
            response_id = message.get("id")
            model = message.get("model")

        elif event_type == "content_block_start":
            index = chunk.get("index", 0)
            block = chunk.get("content_block", {})
            block_type = block.get("type", "text")
            content_blocks[index] = {
                "type": block_type,
                "text": block.get("text", ""),
                "name": block.get("name", ""),
                "input": "",  # Will be accumulated
            }

        elif event_type == "content_block_delta":
            index = chunk.get("index", 0)
            delta = chunk.get("delta", {})
            delta_type = delta.get("type", "")

            if index not in content_blocks:
                content_blocks[index] = {"type": "text", "text": "", "name": "", "input": ""}

            if delta_type == "text_delta":
                content_blocks[index]["text"] += delta.get("text", "")
            elif delta_type == "thinking_delta":
                content_blocks[index]["text"] += delta.get("thinking", "")
            elif delta_type == "input_json_delta":
                content_blocks[index]["input"] += delta.get("partial_json", "")

        elif event_type == "message_delta":
            delta = chunk.get("delta", {})
            stop_reason = delta.get("stop_reason")

    # Build response in Claude format
    content = []
    for idx in sorted(content_blocks.keys()):
        block = content_blocks[idx]
        block_type = block["type"]

        if block_type == "text":
            content.append({"type": "text", "text": block["text"]})
        elif block_type == "thinking":
            content.append({"type": "thinking", "thinking": block["text"]})
        elif block_type == "tool_use":
            input_data = {}
            if block["input"]:
                try:
                    input_data = json.loads(block["input"])
                except json.JSONDecodeError:
                    input_data = {"raw": block["input"]}
            content.append(
                {
                    "type": "tool_use",
                    "name": block["name"],
                    "input": input_data,
                }
            )

    return {
        "id": response_id,
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
    }


def _is_claude_sse(sse_lines: list[str]) -> bool:
    """Detect if SSE lines are in Claude format."""
    for line in sse_lines:
        if line.startswith("data: "):
            data = line[6:]
            try:
                chunk = json.loads(data)
                # Claude events have a "type" field
                if "type" in chunk and chunk["type"] in (
                    "message_start",
                    "content_block_start",
                    "content_block_delta",
                    "message_delta",
                    "message_stop",
                ):
                    return True
                # OpenAI events have "choices" field
                if "choices" in chunk:
                    return False
            except json.JSONDecodeError:
                continue
    return False


def _parse_tool_calls(tool_calls: list[dict] | None) -> list[dict] | None:
    """Parse tool_calls, flattening to {name, arguments} format for frontend."""
    if not tool_calls:
        return None

    parsed = []
    for tc in tool_calls:
        # Extract function name and arguments from OpenAI format
        if "function" in tc and isinstance(tc["function"], dict):
            func = tc["function"]
            name = func.get("name", "")
            arguments = func.get("arguments", {})

            # Decode JSON arguments string to dict
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}  # Keep as raw if not valid JSON

            parsed.append({"name": name, "arguments": arguments})
        else:
            # Already flat format or unknown structure
            parsed.append(tc)
    return parsed


def _iso_to_unix_ms(iso_str: str) -> int:
    """Convert ISO timestamp to Unix milliseconds."""
    # Handle various ISO formats
    iso_str = iso_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_str)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _detect_api_format(record: dict) -> str:
    """Detect whether record is Claude or OpenAI format."""
    request = record.get("request", {})
    response = record.get("response", {})

    # Check streaming response SSE format
    if response and response.get("stream") and "sse_lines" in response:
        if _is_claude_sse(response["sse_lines"]):
            return "claude"
        return "openai"

    # Claude indicators: system field is a list of blocks
    if "system" in request and isinstance(request.get("system"), list):
        return "claude"

    # Claude tools have input_schema instead of function.parameters
    tools = request.get("tools", [])
    if tools and isinstance(tools[0], dict) and "input_schema" in tools[0]:
        return "claude"

    # Check for Claude content block types in messages
    for msg in request.get("messages", []):
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in (
                    "tool_use",
                    "tool_result",
                    "thinking",
                ):
                    return "claude"

    return "openai"


class TraceCooker:
    """Processes trace records into deduplicated visualization format."""

    def __init__(self):
        self.message_hash_to_id: dict[str, str] = {}
        self.tool_hash_to_id: dict[str, str] = {}
        self.messages: list[CookedMessage] = []
        self.tools: list[CookedTool] = []
        self.requests: list[CookedRequest] = []
        self._message_counter = 0
        self._tool_counter = 0

    def _get_or_create_message(self, role: str, content: str, tool_calls: list[dict] | None) -> str:
        """Get existing message ID or create new message, returns ID."""
        mapped_role = _map_role(role, tool_calls)
        parsed_tool_calls = _parse_tool_calls(tool_calls)
        content = content or ""

        msg_hash = _compute_message_hash(mapped_role, content, parsed_tool_calls)

        if msg_hash in self.message_hash_to_id:
            return self.message_hash_to_id[msg_hash]

        msg_id = f"m{self._message_counter}"
        self._message_counter += 1

        msg = CookedMessage(
            id=msg_id,
            role=mapped_role,
            content=content,
            tool_calls=parsed_tool_calls,
        )
        self.messages.append(msg)
        self.message_hash_to_id[msg_hash] = msg_id
        return msg_id

    def _get_or_create_tool(self, name: str, description: str, parameters: dict) -> str:
        """Get existing tool ID or create new tool, returns ID."""
        tool_hash = _compute_tool_hash(name, description, parameters)

        if tool_hash in self.tool_hash_to_id:
            return self.tool_hash_to_id[tool_hash]

        tool_id = f"t{self._tool_counter}"
        self._tool_counter += 1

        tool = CookedTool(
            id=tool_id,
            name=name,
            description=description,
            parameters=parameters,
        )
        self.tools.append(tool)
        self.tool_hash_to_id[tool_hash] = tool_id
        return tool_id

    def _process_request_messages(self, messages: list[dict]) -> list[str]:
        """Process request messages and return list of message IDs.

        Handles content that can be either a string or an array.
        When content is an array, each element is expanded into a separate message.
        """
        msg_ids = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")

            # Handle content as array - expand into multiple messages
            if isinstance(content, list):
                for item in content:
                    item_content = self._extract_content_from_item(item)
                    msg_id = self._get_or_create_message(role, item_content, None)
                    msg_ids.append(msg_id)
                # If there are tool_calls, add a separate message for them
                if tool_calls:
                    msg_id = self._get_or_create_message(role, "", tool_calls)
                    msg_ids.append(msg_id)
            else:
                msg_id = self._get_or_create_message(role, content, tool_calls)
                msg_ids.append(msg_id)
        return msg_ids

    def _extract_content_from_item(self, item: str | dict) -> str:
        """Extract content string from a content array item.

        Handles both plain strings and structured content objects like:
        - {"type": "text", "text": "..."}
        - {"type": "image_url", "image_url": {"url": "..."}}
        """
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            # Text content block
            if item.get("type") == "text":
                return item.get("text", "")
            # Image URL content block
            if item.get("type") == "image_url":
                image_url = item.get("image_url", {})
                url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
                # Truncate base64 data URLs for display
                if url.startswith("data:"):
                    return "[image: base64 data]"
                return f"[image: {url}]"
            # Other types - serialize as JSON
            return json.dumps(item, ensure_ascii=False)
        return str(item)

    def _process_response_message(self, response: dict | None, error: str | None) -> list[str]:
        """Process response and return list of message IDs."""
        if error:
            return [self._get_or_create_message("assistant", f"Error: {error}", None)]

        if not response:
            return [self._get_or_create_message("assistant", "", None)]

        # Handle streaming response - parse SSE lines first
        if response.get("stream") and "sse_lines" in response:
            sse_lines = response["sse_lines"]
            response = _parse_openai_sse(sse_lines)

        choices = response.get("choices", [])
        if not choices:
            return [self._get_or_create_message("assistant", "", None)]

        message = choices[0].get("message", {})
        role = message.get("role", "assistant")
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        return [self._get_or_create_message(role, content, tool_calls)]

    def _process_tools(self, tools: list[dict] | None) -> list[str]:
        """Process tool definitions and return list of tool IDs."""
        if not tools:
            return []

        tool_ids = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                name = func.get("name", "")
                description = func.get("description", "")
                parameters = func.get("parameters", {})

                tool_id = self._get_or_create_tool(name, description, parameters)
                tool_ids.append(tool_id)
        return tool_ids

    # ========== Claude API format processing methods ==========

    def _process_claude_system(self, system: list[dict] | None) -> list[str]:
        """Process Claude's system field into system message IDs."""
        if not system:
            return []

        msg_ids = []
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                content = block.get("text", "")
                msg_id = self._get_or_create_message("system", content, None)
                msg_ids.append(msg_id)
            elif isinstance(block, str):
                msg_id = self._get_or_create_message("system", block, None)
                msg_ids.append(msg_id)
        return msg_ids

    def _process_claude_request_messages(
        self, messages: list[dict], system: list[dict] | None
    ) -> list[str]:
        """Process Claude request messages and return list of message IDs."""
        msg_ids = []

        # First add system messages
        msg_ids.extend(self._process_claude_system(system))

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            # Handle content as string (simple case)
            if isinstance(content, str):
                msg_id = self._get_or_create_message(role, content, None)
                msg_ids.append(msg_id)
                continue

            # Handle content as array of blocks
            if isinstance(content, list):
                msg_ids.extend(self._process_claude_content_blocks(role, content))

        return msg_ids

    def _process_claude_content_blocks(self, role: str, blocks: list[dict]) -> list[str]:
        """Process Claude content blocks and return message IDs.

        Each text block becomes a separate message (consistent with OpenAI handling).
        Thinking blocks become separate messages with role "thinking".
        Tool use blocks are collected into a single tool_use message.
        Tool result blocks become separate tool_result messages.
        """
        msg_ids = []
        tool_calls = []

        for block in blocks:
            if not isinstance(block, dict):
                # Plain string - create message
                content = str(block)
                msg_id = self._get_or_create_message(role, content, None)
                msg_ids.append(msg_id)
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                # Each text block becomes a separate message
                content = block.get("text", "")
                msg_id = self._get_or_create_message(role, content, None)
                msg_ids.append(msg_id)

            elif block_type == "thinking":
                # Create separate thinking message
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    msg_id = self._get_or_create_message("thinking", thinking_text, None)
                    msg_ids.append(msg_id)

            elif block_type == "tool_use":
                # Collect tool calls
                tool_calls.append(
                    {
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                )

            elif block_type == "tool_result":
                # Create separate message with tool_result role
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    # Handle content as array (e.g., multiple text blocks)
                    result_content = "\n".join(
                        b.get("text", str(b)) if isinstance(b, dict) else str(b)
                        for b in result_content
                    )
                msg_id = self._get_or_create_message("tool_result", str(result_content), None)
                msg_ids.append(msg_id)

            elif block_type == "image":
                msg_id = self._get_or_create_message(role, "[image]", None)
                msg_ids.append(msg_id)

            else:
                # Unknown block type - serialize as JSON
                content = json.dumps(block, ensure_ascii=False)
                msg_id = self._get_or_create_message(role, content, None)
                msg_ids.append(msg_id)

        # Create tool_use message if there are tool calls
        if tool_calls:
            msg_id = self._get_or_create_message("tool_use", "", tool_calls)
            msg_ids.append(msg_id)

        return msg_ids

    def _process_claude_response(self, response: dict | None, error: str | None) -> list[str]:
        """Process Claude response and return list of message IDs."""
        if error:
            return [self._get_or_create_message("assistant", f"Error: {error}", None)]

        if not response:
            return [self._get_or_create_message("assistant", "", None)]

        # Handle streaming response - parse SSE lines first
        if response.get("stream") and "sse_lines" in response:
            sse_lines = response["sse_lines"]
            response = _parse_claude_sse(sse_lines)

        content = response.get("content", [])
        if not content:
            return [self._get_or_create_message("assistant", "", None)]

        msg_ids = []
        text_parts = []
        tool_calls = []

        for block in content:
            if not isinstance(block, dict):
                text_parts.append(str(block))
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                text_parts.append(block.get("text", ""))

            elif block_type == "thinking":
                # Create separate thinking message
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    msg_id = self._get_or_create_message("thinking", thinking_text, None)
                    msg_ids.append(msg_id)

            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                )

        # Create assistant message for text/tool_calls
        combined_text = "".join(text_parts).strip()
        if combined_text or tool_calls:
            msg_id = self._get_or_create_message(
                "assistant", combined_text, tool_calls if tool_calls else None
            )
            msg_ids.append(msg_id)
        elif not msg_ids:
            # No content at all - create empty assistant message
            msg_ids.append(self._get_or_create_message("assistant", "", None))

        return msg_ids

    def _process_claude_tools(self, tools: list[dict] | None) -> list[str]:
        """Process Claude tool definitions and return list of tool IDs."""
        if not tools:
            return []

        tool_ids = []
        for tool in tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            # Claude uses input_schema instead of parameters
            parameters = tool.get("input_schema", {})

            tool_id = self._get_or_create_tool(name, description, parameters)
            tool_ids.append(tool_id)
        return tool_ids

    def _process_record_claude(self, record: dict) -> CookedRequest:
        """Process a single Claude API trace record."""
        request = record.get("request", {})
        response = record.get("response")
        error = record.get("error")

        # Process request messages (with system)
        messages = request.get("messages", [])
        system = request.get("system")
        request_msg_ids = self._process_claude_request_messages(messages, system)

        # Process response messages
        response_msg_ids = self._process_claude_response(response, error)

        # Process tools
        tools = request.get("tools", [])
        tool_ids = self._process_claude_tools(tools)

        # Create request record
        record_id = record.get("id", "")
        timestamp = _iso_to_unix_ms(record.get("timestamp", ""))
        model = request.get("model", "")
        duration_ms = record.get("duration_ms", 0)

        return CookedRequest(
            id=record_id,
            parent_id=None,
            timestamp=timestamp,
            request_messages=request_msg_ids,
            response_messages=response_msg_ids,
            model=model,
            tools=tool_ids,
            duration_ms=duration_ms,
        )

    def _process_record(self, record: dict, api_format: str = "auto") -> CookedRequest:
        """Process a single trace record, returns CookedRequest (parent_id not set)."""
        # Determine format
        if api_format == "auto":
            detected_format = _detect_api_format(record)
        else:
            detected_format = api_format

        # Dispatch to format-specific handler
        if detected_format == "claude":
            return self._process_record_claude(record)

        # OpenAI format (default)
        request = record.get("request", {})
        response = record.get("response")
        error = record.get("error")

        # Process request messages
        messages = request.get("messages", [])
        request_msg_ids = self._process_request_messages(messages)

        # Process response messages
        response_msg_ids = self._process_response_message(response, error)

        # Process tools
        tools = request.get("tools", [])
        tool_ids = self._process_tools(tools)

        # Create request record (parent_id will be set later)
        record_id = record.get("id", "")
        timestamp = _iso_to_unix_ms(record.get("timestamp", ""))
        model = request.get("model", "")
        duration_ms = record.get("duration_ms", 0)

        return CookedRequest(
            id=record_id,
            parent_id=None,
            timestamp=timestamp,
            request_messages=request_msg_ids,
            response_messages=response_msg_ids,
            model=model,
            tools=tool_ids,
            duration_ms=duration_ms,
        )

    def cook(self, records: list[dict], api_format: str = "auto") -> CookedOutput:
        """Process all records and return deduplicated output."""
        # Step 1: Process all records
        for record in records:
            cooked_request = self._process_record(record, api_format)
            self.requests.append(cooked_request)

        # Step 2: Sort by timestamp
        self.requests.sort(key=lambda r: r.timestamp)

        # Step 3: Analyze dependencies
        self._analyze_dependencies()

        return CookedOutput(
            messages=self.messages,
            tools=self.tools,
            requests=self.requests,
        )

    # Dependency analysis parameters
    TOOL_DIFF_PENALTY = 0.5  # Penalty per different tool
    RELATIVE_THRESHOLD = 0.5  # Edit distance threshold as ratio of message count

    def _analyze_dependencies(self) -> None:
        """Analyze request dependencies and set parent_id for each request."""
        for idx, req in enumerate(self.requests):
            if idx == 0:
                req.parent_id = None
            else:
                req.parent_id = self._find_parent(req, self.requests[:idx])

    def _find_parent(self, curr: CookedRequest, candidates: list[CookedRequest]) -> str | None:
        """Find the best parent for current request.

        Args:
            curr: Current request
            candidates: Requests earlier than curr (sorted by timestamp ascending)

        Returns:
            parent_id or None (becomes new root if no good match)
        """
        # Filter: only consider candidates with same model
        same_model_candidates = [c for c in candidates if c.model == curr.model]

        if not same_model_candidates:
            return None  # No same-model candidate, become new root

        # Optimization: check prefix relationship first (from most recent)
        for c in reversed(same_model_candidates):
            expected_prefix = self._build_expected_prefix(c)
            if self._is_prefix(expected_prefix, curr.request_messages):
                return c.id

        # Fallback: use combined score to find most similar parent
        best_score = float("-inf")
        best_parent_id = None

        for c in reversed(same_model_candidates):  # From most recent, same score picks latest
            score = self._match_score(curr, c)
            if score > best_score:
                best_score = score
                best_parent_id = c.id

        # Forest support: become new root if score is too low
        threshold = -len(curr.request_messages) * self.RELATIVE_THRESHOLD
        if best_score < threshold:
            return None

        return best_parent_id

    def _build_expected_prefix(self, candidate: CookedRequest) -> list[str]:
        """Build expected message prefix.

        If candidate has response_messages, prefix = request_messages + response_messages
        Otherwise just request_messages
        """
        prefix = list(candidate.request_messages)
        if candidate.response_messages:
            prefix.extend(candidate.response_messages)
        return prefix

    def _is_prefix(self, prefix: list[str], messages: list[str]) -> bool:
        """Check if prefix is a prefix of messages."""
        if len(prefix) > len(messages):
            return False
        return messages[: len(prefix)] == prefix

    def _match_score(self, curr: CookedRequest, candidate: CookedRequest) -> float:
        """Compute combined match score (higher is more similar).

        Score = message_score + tool_score
        - message_score: negative edit distance
        - tool_score: penalty for tool differences
        """
        # Message score: negative edit distance
        a = self._build_expected_prefix(candidate)
        b = curr.request_messages
        message_score = -self._levenshtein(a, b)

        # Tool score: penalty for different tools
        curr_tools = set(curr.tools)
        candidate_tools = set(candidate.tools)
        tool_diff = len(curr_tools.symmetric_difference(candidate_tools))
        tool_score = -self.TOOL_DIFF_PENALTY * tool_diff

        return message_score + tool_score

    def _levenshtein(self, a: list[str], b: list[str]) -> int:
        """Compute Levenshtein distance between two lists.

        Operations: add, delete, replace
        """
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],  # delete
                        dp[i][j - 1],  # add
                        dp[i - 1][j - 1],  # replace
                    )

        return dp[m][n]


def cook_traces(input_path: str, output_path: str, api_format: str = "auto") -> None:
    """Main entry point: read JSONL/JSON traces and write cooked JSON output.

    Args:
        input_path: Path to input JSONL/JSON trace file
        output_path: Path to output JSON file
        api_format: API format of input traces: "auto", "openai", or "claude"
    """
    input_file = Path(input_path)
    output_file = Path(output_path)

    # Read records
    records = []
    content = input_file.read_text(encoding="utf-8")

    # Try to parse as JSON array first (single JSON file)
    try:
        data = json.loads(content)
        if isinstance(data, list):
            records = data
        else:
            # Single record
            records = [data]
    except json.JSONDecodeError:
        # Parse as JSONL
        for line in content.strip().split("\n"):
            if line.strip():
                records.append(json.loads(line))

    # Process records
    cooker = TraceCooker()
    output = cooker.cook(records, api_format)

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"Processed {len(records)} records")
    print(f"  Messages: {len(output.messages)} (deduplicated)")
    print(f"  Tools: {len(output.tools)} (deduplicated)")
    print(f"  Requests: {len(output.requests)}")
    print(f"Output written to: {output_path}")
