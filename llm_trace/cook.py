"""Preprocessing module to convert JSONL traces to visualization-ready JSON."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CookedMessage:
    """Deduplicated message with stable ID."""

    id: str
    role: str  # "system" | "user" | "tool_use" | "tool_result" | "assistant"
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
    response_message: str  # Message ID
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

    def _process_response_message(self, response: dict | None, error: str | None) -> str:
        """Process response and return message ID."""
        if error:
            return self._get_or_create_message("assistant", f"Error: {error}", None)

        if not response:
            return self._get_or_create_message("assistant", "", None)

        choices = response.get("choices", [])
        if not choices:
            return self._get_or_create_message("assistant", "", None)

        message = choices[0].get("message", {})
        role = message.get("role", "assistant")
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        return self._get_or_create_message(role, content, tool_calls)

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

    def _process_record(self, record: dict) -> CookedRequest:
        """Process a single trace record, returns CookedRequest (parent_id not set)."""
        request = record.get("request", {})
        response = record.get("response")
        error = record.get("error")

        # Process request messages
        messages = request.get("messages", [])
        request_msg_ids = self._process_request_messages(messages)

        # Process response message
        response_msg_id = self._process_response_message(response, error)

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
            response_message=response_msg_id,
            model=model,
            tools=tool_ids,
            duration_ms=duration_ms,
        )

    def cook(self, records: list[dict]) -> CookedOutput:
        """Process all records and return deduplicated output."""
        # Step 1: Process all records
        for record in records:
            cooked_request = self._process_record(record)
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
            parent_id or None
        """
        # Optimization: check prefix relationship first (from most recent)
        for c in reversed(candidates):
            expected_prefix = self._build_expected_prefix(c)
            if self._is_prefix(expected_prefix, curr.request_messages):
                return c.id

        # Fallback: use edit distance to find most similar parent
        best_score = float("-inf")
        best_parent_id = None

        for c in reversed(candidates):  # From most recent, same score picks latest
            score = self._match_score(curr, c)
            if score > best_score:
                best_score = score
                best_parent_id = c.id

        return best_parent_id

    def _build_expected_prefix(self, candidate: CookedRequest) -> list[str]:
        """Build expected message prefix.

        If candidate has response_message, prefix = request_messages + [response_message]
        Otherwise just request_messages
        """
        prefix = list(candidate.request_messages)
        if candidate.response_message is not None:
            prefix.append(candidate.response_message)
        return prefix

    def _is_prefix(self, prefix: list[str], messages: list[str]) -> bool:
        """Check if prefix is a prefix of messages."""
        if len(prefix) > len(messages):
            return False
        return messages[: len(prefix)] == prefix

    def _match_score(self, curr: CookedRequest, candidate: CookedRequest) -> float:
        """Compute match score using negative edit distance (higher is more similar).

        Calculates edit operations needed to transform A to B, returns negative.
        A: candidate.request_messages + [candidate.response_message] (if exists)
        B: curr.request_messages
        """
        a = self._build_expected_prefix(candidate)
        b = curr.request_messages

        edit_distance = self._levenshtein(a, b)
        return -edit_distance

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


def cook_traces(input_path: str, output_path: str) -> None:
    """Main entry point: read JSONL/JSON traces and write cooked JSON output."""
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
    output = cooker.cook(records)

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"Processed {len(records)} records")
    print(f"  Messages: {len(output.messages)} (deduplicated)")
    print(f"  Tools: {len(output.tools)} (deduplicated)")
    print(f"  Requests: {len(output.requests)}")
    print(f"Output written to: {output_path}")
