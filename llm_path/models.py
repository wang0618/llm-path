"""Data models for LLM trace records."""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TraceRecord:
    """Represents a single LLM API request/response pair."""

    request: dict[str, Any]
    response: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert the record to a dictionary for JSON serialization."""
        return asdict(self)
