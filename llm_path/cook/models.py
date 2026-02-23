"""Data models for cooked trace output."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ApiFormat = Literal["auto", "openai", "claude", "gemini"]


@dataclass
class CookedMessage:
    """Deduplicated message with stable ID."""

    id: str
    role: str  # "system" | "user" | "tool_use" | "tool_result" | "assistant" | "thinking"
    content: str
    tool_calls: list[dict] | None = None  # Each has: name, arguments, id (optional)
    tool_use_id: str | None = None  # For tool_result: references the tool_use it responds to
    is_error: bool | None = None  # For tool_result: whether the tool execution failed


@dataclass
class CookedTool:
    """Deduplicated tool definition with stable ID."""

    id: str
    name: str
    description: str
    parameters: dict
    is_server_side: bool = False  # True for server-side tools (e.g., Gemini's googleSearch)


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
