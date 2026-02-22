"""OpenAI API format provider."""

import json

from ..base import BaseProvider, iso_to_unix_ms
from ..deduplicator import MessageDeduplicator, ToolDeduplicator
from ..models import CookedRequest


def _map_role(role: str, tool_calls: list[dict] | None) -> str:
    """Map original role to visualization role."""
    if role == "assistant" and tool_calls:
        return "tool_use"
    if role == "tool":
        return "tool_result"
    return role


def _parse_tool_calls(tool_calls: list[dict] | None) -> list[dict] | None:
    """Parse tool_calls, flattening to {name, arguments, id} format for frontend."""
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

            call = {"name": name, "arguments": arguments}
            # Preserve tool call ID from OpenAI format
            if "id" in tc:
                call["id"] = tc["id"]
            parsed.append(call)
        else:
            # Already flat format or unknown structure
            parsed.append(tc)
    return parsed


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


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI API format."""

    @staticmethod
    def detect(record: dict) -> bool:
        """Detect if record is in OpenAI format.

        OpenAI is the default/fallback format, so this returns True
        for any record that isn't explicitly Claude format.
        """
        request = record.get("request", {})
        response = record.get("response", {})

        # Check streaming response SSE format for Claude indicators
        if response and response.get("stream") and "sse_lines" in response:
            for line in response["sse_lines"]:
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
                            return False  # This is Claude format
                        # OpenAI events have "choices" field
                        if "choices" in chunk:
                            return True
                    except json.JSONDecodeError:
                        continue

        # Check for Claude indicators
        # Claude: system field is a list of blocks
        if "system" in request and isinstance(request.get("system"), list):
            return False

        # Claude tools have input_schema instead of function.parameters
        tools = request.get("tools", [])
        if tools and isinstance(tools[0], dict) and "input_schema" in tools[0]:
            return False

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
                        return False

        return True  # Default to OpenAI

    def process_record(
        self,
        record: dict,
        message_dedup: MessageDeduplicator,
        tool_dedup: ToolDeduplicator,
    ) -> CookedRequest:
        """Process an OpenAI format trace record."""
        request = record.get("request", {})
        response = record.get("response")
        error = record.get("error")

        # Process request messages
        messages = request.get("messages", [])
        request_msg_ids = self._process_request_messages(messages, message_dedup)

        # Process response messages
        response_msg_ids = self._process_response_message(response, error, message_dedup)

        # Process tools
        tools = request.get("tools", [])
        tool_ids = self._process_tools(tools, tool_dedup)

        # Create request record (parent_id will be set later)
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

    def _process_request_messages(
        self, messages: list[dict], message_dedup: MessageDeduplicator
    ) -> list[str]:
        """Process request messages and return list of message IDs.

        Handles content that can be either a string or an array.
        When content is an array, each element is expanded into a separate message.
        """
        msg_ids = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            # OpenAI format: tool role has tool_call_id to reference the tool call
            tool_call_id = msg.get("tool_call_id")

            # Handle content as array - expand into multiple messages
            if isinstance(content, list):
                for item in content:
                    item_content = self._extract_content_from_item(item)
                    msg_id = message_dedup.get_or_create(role, item_content)
                    msg_ids.append(msg_id)
                # If there are tool_calls, add a separate message for them
                if tool_calls:
                    mapped_role = _map_role(role, tool_calls)
                    parsed_tool_calls = _parse_tool_calls(tool_calls)
                    msg_id = message_dedup.get_or_create(mapped_role, "", parsed_tool_calls)
                    msg_ids.append(msg_id)
            else:
                mapped_role = _map_role(role, tool_calls)
                parsed_tool_calls = _parse_tool_calls(tool_calls)
                msg_id = message_dedup.get_or_create(
                    mapped_role, content, parsed_tool_calls, tool_use_id=tool_call_id
                )
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

    def _process_response_message(
        self,
        response: dict | None,
        error: str | None,
        message_dedup: MessageDeduplicator,
    ) -> list[str]:
        """Process response and return list of message IDs."""
        if error:
            return [message_dedup.get_or_create("assistant", f"Error: {error}")]

        if not response:
            return [message_dedup.get_or_create("assistant", "")]

        # Handle streaming response - parse SSE lines first
        if response.get("stream") and "sse_lines" in response:
            sse_lines = response["sse_lines"]
            response = _parse_openai_sse(sse_lines)

        choices = response.get("choices", [])
        if not choices:
            return [message_dedup.get_or_create("assistant", "")]

        message = choices[0].get("message", {})
        role = message.get("role", "assistant")
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        # Create a single message with both content and tool_calls
        mapped_role = _map_role(role, tool_calls)
        parsed_tool_calls = _parse_tool_calls(tool_calls)
        msg_id = message_dedup.get_or_create(mapped_role, content or "", parsed_tool_calls)
        return [msg_id]

    def _process_tools(self, tools: list[dict], tool_dedup: ToolDeduplicator) -> list[str]:
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

                tool_id = tool_dedup.get_or_create(name, description, parameters)
                tool_ids.append(tool_id)
        return tool_ids
