"""Deduplication logic for messages and tools."""

import hashlib
import json

from .models import CookedMessage, CookedTool


def _compute_message_hash(
    role: str,
    content: str,
    tool_calls: list[dict] | None,
    tool_use_id: str | None = None,
    is_error: bool | None = None,
) -> str:
    """Compute stable hash for message deduplication."""
    data = {
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def _compute_tool_hash(
    name: str, description: str, parameters: dict, is_server_side: bool = False
) -> str:
    """Compute stable hash for tool deduplication."""
    data = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "is_server_side": is_server_side,
    }
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


class MessageDeduplicator:
    """Handles message deduplication via hash-based ID generation."""

    def __init__(self) -> None:
        self._hash_to_id: dict[str, str] = {}
        self._messages: list[CookedMessage] = []
        self._counter = 0

    def get_or_create(
        self,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_use_id: str | None = None,
        is_error: bool | None = None,
    ) -> str:
        """Get existing message ID or create new message, returns ID.

        Args:
            role: Message role (already mapped to standard roles)
            content: Message content string
            tool_calls: Optional list of tool calls (already parsed)
            tool_use_id: For tool_result, ID of the tool_use it responds to
            is_error: For tool_result, whether the tool execution failed

        Returns:
            Message ID (e.g., "m0", "m1", ...)
        """
        content = content or ""
        msg_hash = _compute_message_hash(role, content, tool_calls, tool_use_id, is_error)

        if msg_hash in self._hash_to_id:
            return self._hash_to_id[msg_hash]

        msg_id = f"m{self._counter}"
        self._counter += 1

        msg = CookedMessage(
            id=msg_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_use_id=tool_use_id,
            is_error=is_error,
        )
        self._messages.append(msg)
        self._hash_to_id[msg_hash] = msg_id
        return msg_id

    @property
    def messages(self) -> list[CookedMessage]:
        """Return all deduplicated messages."""
        return self._messages


class ToolDeduplicator:
    """Handles tool definition deduplication via hash-based ID generation."""

    def __init__(self) -> None:
        self._hash_to_id: dict[str, str] = {}
        self._tools: list[CookedTool] = []
        self._counter = 0

    def get_or_create(
        self,
        name: str,
        description: str,
        parameters: dict,
        is_server_side: bool = False,
    ) -> str:
        """Get existing tool ID or create new tool, returns ID.

        Args:
            name: Tool name
            description: Tool description
            parameters: Tool parameter schema (JSON Schema)
            is_server_side: True for server-side/builtin tools (e.g., Gemini's googleSearch)

        Returns:
            Tool ID (e.g., "t0", "t1", ...)
        """
        tool_hash = _compute_tool_hash(name, description, parameters, is_server_side)

        if tool_hash in self._hash_to_id:
            return self._hash_to_id[tool_hash]

        tool_id = f"t{self._counter}"
        self._counter += 1

        tool = CookedTool(
            id=tool_id,
            name=name,
            description=description,
            parameters=parameters,
            is_server_side=is_server_side,
        )
        self._tools.append(tool)
        self._hash_to_id[tool_hash] = tool_id
        return tool_id

    @property
    def tools(self) -> list[CookedTool]:
        """Return all deduplicated tools."""
        return self._tools
