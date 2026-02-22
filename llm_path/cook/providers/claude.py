"""Claude API format provider."""

import json

from ..base import BaseProvider, iso_to_unix_ms
from ..deduplicator import MessageDeduplicator, ToolDeduplicator
from ..models import CookedRequest


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
                "id": block.get("id"),  # tool_use ID
            }

        elif event_type == "content_block_delta":
            index = chunk.get("index", 0)
            delta = chunk.get("delta", {})
            delta_type = delta.get("type", "")

            if index not in content_blocks:
                content_blocks[index] = {
                    "type": "text",
                    "text": "",
                    "name": "",
                    "input": "",
                }

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
            tool_use_block = {
                "type": "tool_use",
                "name": block["name"],
                "input": input_data,
            }
            if block.get("id"):
                tool_use_block["id"] = block["id"]
            content.append(tool_use_block)

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


class ClaudeProvider(BaseProvider):
    """Provider for Claude API format."""

    @staticmethod
    def detect(record: dict) -> bool:
        """Detect if record is in Claude format."""
        request = record.get("request", {})
        response = record.get("response", {})

        # Check streaming response SSE format
        if response and response.get("stream") and "sse_lines" in response:
            if _is_claude_sse(response["sse_lines"]):
                return True

        # Claude indicators: system field is a list of blocks
        if "system" in request and isinstance(request.get("system"), list):
            return True

        # Claude tools have input_schema instead of function.parameters
        tools = request.get("tools", [])
        if tools and isinstance(tools[0], dict) and "input_schema" in tools[0]:
            return True

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
                        return True

        return False

    def process_record(
        self,
        record: dict,
        message_dedup: MessageDeduplicator,
        tool_dedup: ToolDeduplicator,
    ) -> CookedRequest:
        """Process a Claude format trace record."""
        request = record.get("request", {})
        response = record.get("response")
        error = record.get("error")

        # Process request messages (with system)
        messages = request.get("messages", [])
        system = request.get("system")
        request_msg_ids = self._process_request_messages(messages, system, message_dedup)

        # Process response messages
        response_msg_ids = self._process_response(response, error, message_dedup)

        # Process tools
        tools = request.get("tools", [])
        tool_ids = self._process_tools(tools, tool_dedup)

        # Create request record
        record_id = record.get("id", "")
        timestamp = iso_to_unix_ms(record.get("timestamp", ""))
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

    def _process_system(
        self, system: list[dict] | None, message_dedup: MessageDeduplicator
    ) -> list[str]:
        """Process Claude's system field into system message IDs."""
        if not system:
            return []

        msg_ids = []
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                content = block.get("text", "")
                msg_id = message_dedup.get_or_create("system", content)
                msg_ids.append(msg_id)
            elif isinstance(block, str):
                msg_id = message_dedup.get_or_create("system", block)
                msg_ids.append(msg_id)
        return msg_ids

    def _process_request_messages(
        self,
        messages: list[dict],
        system: list[dict] | None,
        message_dedup: MessageDeduplicator,
    ) -> list[str]:
        """Process Claude request messages and return list of message IDs."""
        msg_ids = []

        # First add system messages
        msg_ids.extend(self._process_system(system, message_dedup))

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            # Handle content as string (simple case)
            if isinstance(content, str):
                msg_id = message_dedup.get_or_create(role, content)
                msg_ids.append(msg_id)
                continue

            # Handle content as array of blocks
            if isinstance(content, list):
                msg_ids.extend(self._process_content_blocks(role, content, message_dedup))

        return msg_ids

    def _process_content_blocks(
        self, role: str, blocks: list[dict], message_dedup: MessageDeduplicator
    ) -> list[str]:
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
                msg_id = message_dedup.get_or_create(role, content)
                msg_ids.append(msg_id)
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                # Each text block becomes a separate message
                content = block.get("text", "")
                msg_id = message_dedup.get_or_create(role, content)
                msg_ids.append(msg_id)

            elif block_type == "thinking":
                # Create separate thinking message
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    msg_id = message_dedup.get_or_create("thinking", thinking_text)
                    msg_ids.append(msg_id)

            elif block_type == "tool_use":
                # Collect tool calls with their IDs
                tool_call = {
                    "name": block.get("name", ""),
                    "arguments": block.get("input", {}),
                }
                if "id" in block:
                    tool_call["id"] = block["id"]
                tool_calls.append(tool_call)

            elif block_type == "tool_result":
                # Create separate message with tool_result role
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    # Handle content as array (e.g., multiple text blocks)
                    result_content = "\n".join(
                        b.get("text", str(b)) if isinstance(b, dict) else str(b)
                        for b in result_content
                    )
                # Extract tool_use_id reference and error status
                tool_use_id = block.get("tool_use_id")
                is_error = block.get("is_error")
                msg_id = message_dedup.get_or_create(
                    "tool_result",
                    str(result_content),
                    tool_use_id=tool_use_id,
                    is_error=is_error,
                )
                msg_ids.append(msg_id)

            elif block_type == "image":
                msg_id = message_dedup.get_or_create(role, "[image]")
                msg_ids.append(msg_id)

            else:
                # Unknown block type - serialize as JSON
                content = json.dumps(block, ensure_ascii=False)
                msg_id = message_dedup.get_or_create(role, content)
                msg_ids.append(msg_id)

        # Create tool_use message if there are tool calls
        if tool_calls:
            msg_id = message_dedup.get_or_create("tool_use", "", tool_calls)
            msg_ids.append(msg_id)

        return msg_ids

    def _process_response(
        self,
        response: dict | None,
        error: str | None,
        message_dedup: MessageDeduplicator,
    ) -> list[str]:
        """Process Claude response and return list of message IDs."""
        if error:
            return [message_dedup.get_or_create("assistant", f"Error: {error}")]

        if not response:
            return [message_dedup.get_or_create("assistant", "")]

        # Handle streaming response - parse SSE lines first
        if response.get("stream") and "sse_lines" in response:
            sse_lines = response["sse_lines"]
            response = _parse_claude_sse(sse_lines)

        content = response.get("content", [])
        if not content:
            return [message_dedup.get_or_create("assistant", "")]

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
                    msg_id = message_dedup.get_or_create("thinking", thinking_text)
                    msg_ids.append(msg_id)

            elif block_type == "tool_use":
                tool_call = {
                    "name": block.get("name", ""),
                    "arguments": block.get("input", {}),
                }
                if "id" in block:
                    tool_call["id"] = block["id"]
                tool_calls.append(tool_call)

        # Split text and tool_calls into separate messages (consistent with request handling)
        combined_text = "".join(text_parts)
        if combined_text:
            msg_id = message_dedup.get_or_create("assistant", combined_text)
            msg_ids.append(msg_id)
        if tool_calls:
            msg_id = message_dedup.get_or_create("tool_use", "", tool_calls)
            msg_ids.append(msg_id)
        # If no content at all (no text, tool_calls, or thinking), create empty assistant message
        if not msg_ids:
            msg_ids.append(message_dedup.get_or_create("assistant", ""))

        return msg_ids

    def _process_tools(self, tools: list[dict], tool_dedup: ToolDeduplicator) -> list[str]:
        """Process Claude tool definitions and return list of tool IDs."""
        if not tools:
            return []

        tool_ids = []
        for tool in tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            # Claude uses input_schema instead of parameters
            parameters = tool.get("input_schema", {})

            tool_id = tool_dedup.get_or_create(name, description, parameters)
            tool_ids.append(tool_id)
        return tool_ids
