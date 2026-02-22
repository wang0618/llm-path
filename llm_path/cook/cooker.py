"""Main trace cooker that coordinates providers, deduplication, and dependency analysis."""

import json
from pathlib import Path

from .deduplicator import MessageDeduplicator, ToolDeduplicator
from .dependency import DependencyAnalyzer
from .models import ApiFormat, CookedOutput, CookedRequest
from .providers import get_provider


class TraceCooker:
    """Processes trace records into deduplicated visualization format.

    This class coordinates:
    - Provider detection and selection
    - Message and tool deduplication
    - Request dependency analysis

    It does NOT know provider-specific details - all format handling is delegated to providers.
    """

    def __init__(self) -> None:
        self._message_dedup = MessageDeduplicator()
        self._tool_dedup = ToolDeduplicator()
        self._requests: list[CookedRequest] = []
        self._dependency_analyzer = DependencyAnalyzer()

    def cook(self, records: list[dict], api_format: ApiFormat = "auto") -> CookedOutput:
        """Process all records and return deduplicated output.

        Args:
            records: List of raw trace records
            api_format: API format ("auto", "openai", or "claude")

        Returns:
            CookedOutput with deduplicated messages, tools, and requests
        """
        # Step 1: Process all records
        for record in records:
            cooked_request = self._process_record(record, api_format)
            self._requests.append(cooked_request)

        # Step 2: Sort by timestamp
        self._requests.sort(key=lambda r: r.timestamp)

        # Step 3: Analyze dependencies
        self._dependency_analyzer.analyze(self._requests)

        return CookedOutput(
            messages=self._message_dedup.messages,
            tools=self._tool_dedup.tools,
            requests=self._requests,
        )

    def _process_record(self, record: dict, api_format: ApiFormat) -> CookedRequest:
        """Process a single trace record using the appropriate provider.

        Args:
            record: Raw trace record
            api_format: API format hint

        Returns:
            CookedRequest with parent_id set to None (dependency analysis done later)
        """
        # Get the appropriate provider
        provider_cls = get_provider(api_format, record)
        provider = provider_cls()

        # Let the provider handle all format-specific details
        return provider.process_record(record, self._message_dedup, self._tool_dedup)


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
    # Cast api_format to ApiFormat type
    output = cooker.cook(records, api_format)  # type: ignore[arg-type]

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"Processed {len(records)} records")
    print(f"  Messages: {len(output.messages)} (deduplicated)")
    print(f"  Tools: {len(output.tools)} (deduplicated)")
    print(f"  Requests: {len(output.requests)}")
    print(f"Output written to: {output_path}")
