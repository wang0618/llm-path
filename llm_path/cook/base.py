"""Base provider interface for trace processing."""

from abc import ABC, abstractmethod
from datetime import datetime

from .deduplicator import MessageDeduplicator, ToolDeduplicator
from .models import CookedRequest


def iso_to_unix_ms(iso_str: str) -> int:
    """Convert ISO timestamp to Unix milliseconds."""
    iso_str = iso_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_str)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


class BaseProvider(ABC):
    """Abstract base class for API format providers.

    Each provider handles a specific API format (OpenAI, Claude, etc.) and is responsible for:
    - Detecting if a record matches its format
    - Parsing raw records into standardized CookedRequest objects
    - Handling SSE parsing internally (if streaming)
    - Extracting and normalizing messages, tools, and responses
    """

    @staticmethod
    @abstractmethod
    def detect(record: dict) -> bool:
        """Detect if this provider can handle the given record.

        Args:
            record: Raw trace record

        Returns:
            True if this provider can process the record
        """
        pass

    @abstractmethod
    def process_record(
        self,
        record: dict,
        message_dedup: MessageDeduplicator,
        tool_dedup: ToolDeduplicator,
    ) -> CookedRequest:
        """Process a single raw trace record into a CookedRequest.

        This method handles all format-specific details:
        - Detecting if response is streaming and parsing SSE
        - Extracting request messages in provider format
        - Extracting response messages in provider format
        - Processing tool definitions
        - Normalizing to CookedRequest format

        The caller (TraceCooker) does not need to know any provider-specific details.

        Args:
            record: Raw trace record
            message_dedup: MessageDeduplicator for creating/reusing message IDs
            tool_dedup: ToolDeduplicator for creating/reusing tool IDs

        Returns:
            CookedRequest with parent_id set to None (dependency analysis done later)
        """
        pass
