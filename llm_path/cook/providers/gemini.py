"""Gemini API format provider."""

import json

from ..base import BaseProvider, iso_to_unix_ms
from ..deduplicator import MessageDeduplicator, ToolDeduplicator
from ..models import CookedRequest


class GeminiProvider(BaseProvider):
    """Provider for Gemini API format.

    Gemini format differences from OpenAI/Claude:
    - Messages are in `contents` (not `messages`)
    - Role values: `user`, `model` (not `assistant`)
    - Content is in `parts` array, each with `text`, `function_call`, or `function_response`
    - System prompt is in `system_instruction.parts`
    - Tools are in `tools[].function_declarations`
    - Response is in `response.candidates[].content`
    - Thinking is indicated by `thoughtSignature` (no actual content exposed)
    """

    @staticmethod
    def detect(record: dict) -> bool:
        """Detect if record is in Gemini format.

        Gemini indicators:
        - Request has `contents` instead of `messages`
        - Request has `system_instruction` instead of `system`
        - Tools have `function_declarations` array
        - Response has `candidates` with `content.parts`
        """
        request = record.get("request", {})
        response = record.get("response", {})

        # Check for Gemini-specific request structure
        if "contents" in request:
            return True

        # Check for system_instruction (Gemini style)
        if "system_instruction" in request:
            return True

        # Check for Gemini tools format
        tools = request.get("tools", [])
        if tools and isinstance(tools, list) and isinstance(tools[0], dict):
            if "function_declarations" in tools[0]:
                return True

        # Check for Gemini response format
        if "candidates" in response:
            candidates = response.get("candidates", [])
            if candidates and isinstance(candidates[0], dict):
                content = candidates[0].get("content", {})
                if "parts" in content and "role" in content:
                    return True

        # Check for modelVersion (Gemini specific)
        if "modelVersion" in response:
            return True

        return False

    def process_record(
        self,
        record: dict,
        message_dedup: MessageDeduplicator,
        tool_dedup: ToolDeduplicator,
    ) -> CookedRequest:
        """Process a Gemini format trace record."""
        request = record.get("request", {})
        response = record.get("response", {})
        error = record.get("error")

        # Process system instruction
        system_instruction = request.get("system_instruction")
        system_msg_ids = self._process_system_instruction(system_instruction, message_dedup)

        # Process request messages (contents)
        contents = request.get("contents", [])
        request_msg_ids = self._process_contents(contents, message_dedup)

        # Prepend system messages
        request_msg_ids = system_msg_ids + request_msg_ids

        # Process response messages
        response_msg_ids = self._process_response(response, error, message_dedup)

        # Process tools
        tools = request.get("tools", [])
        tool_ids = self._process_tools(tools, tool_dedup)

        # Create request record
        record_id = record.get("id", "")
        timestamp = iso_to_unix_ms(record.get("timestamp", ""))
        # Model from response.modelVersion or request.model
        model = response.get("modelVersion", "") or request.get("model", "")
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

    def _process_system_instruction(
        self, system_instruction: dict | None, message_dedup: MessageDeduplicator
    ) -> list[str]:
        """Process Gemini's system_instruction into system message IDs."""
        if not system_instruction:
            return []

        msg_ids = []
        parts = system_instruction.get("parts", [])
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                content = part.get("text", "")
                if content:
                    msg_id = message_dedup.get_or_create("system", content)
                    msg_ids.append(msg_id)
            elif isinstance(part, str):
                msg_id = message_dedup.get_or_create("system", part)
                msg_ids.append(msg_id)
        return msg_ids

    def _process_contents(
        self, contents: list[dict], message_dedup: MessageDeduplicator
    ) -> list[str]:
        """Process Gemini contents array into message IDs."""
        msg_ids = []

        for content in contents:
            role = content.get("role", "")
            parts = content.get("parts", [])

            # Map Gemini roles to standard roles
            # model -> assistant, user -> user, None -> depends on content
            mapped_role = self._map_role(role)

            msg_ids.extend(self._process_parts(parts, mapped_role, message_dedup))

        return msg_ids

    def _map_role(self, role: str | None) -> str:
        """Map Gemini role to standard role."""
        if role == "model":
            return "assistant"
        if role == "user":
            return "user"
        # None role is typically for function responses
        return "user"

    def _process_parts(
        self, parts: list[dict], base_role: str, message_dedup: MessageDeduplicator
    ) -> list[str]:
        """Process Gemini parts array into message IDs.

        Parts can contain:
        - text: regular text content
        - function_call/functionCall: tool use
        - function_response/functionResponse: tool result
        - thoughtSignature: indicates thinking (no content)
        """
        msg_ids = []
        text_content = []
        tool_calls = []

        for part in parts:
            if not isinstance(part, dict):
                continue

            # Handle text content
            if "text" in part:
                text = part.get("text", "")
                if text:
                    text_content.append(text)

            # Handle function call (tool use) - check both naming conventions
            func_call = part.get("function_call") or part.get("functionCall")
            if func_call:
                tool_call = {
                    "name": func_call.get("name", ""),
                    "arguments": func_call.get("args", {}),
                }
                tool_calls.append(tool_call)

            # Handle function response (tool result) - check both naming conventions
            func_response = part.get("function_response") or part.get("functionResponse")
            if func_response:
                name = func_response.get("name", "")
                response_data = func_response.get("response", {})
                # Extract content from response
                if isinstance(response_data, dict):
                    result_content = response_data.get(
                        "content", json.dumps(response_data, ensure_ascii=False)
                    )
                else:
                    result_content = str(response_data)

                msg_id = message_dedup.get_or_create(
                    "tool_result",
                    result_content,
                    tool_use_id=name,  # Use function name as reference
                )
                msg_ids.append(msg_id)

            # thoughtSignature indicates thinking but doesn't contain actual content
            # We skip it as there's no text to display

        # Create message for text content
        if text_content:
            combined_text = "".join(text_content)
            msg_id = message_dedup.get_or_create(base_role, combined_text)
            msg_ids.append(msg_id)

        # Create message for tool calls
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
        """Process Gemini response and return list of message IDs."""
        if error:
            return [message_dedup.get_or_create("assistant", f"Error: {error}")]

        if not response:
            return [message_dedup.get_or_create("assistant", "")]

        candidates = response.get("candidates", [])
        if not candidates:
            return [message_dedup.get_or_create("assistant", "")]

        # Get the first candidate's content
        first_candidate = candidates[0]
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])

        if not parts:
            return [message_dedup.get_or_create("assistant", "")]

        # Process parts as response
        return self._process_parts(parts, "assistant", message_dedup)

    def _process_tools(self, tools: list[dict], tool_dedup: ToolDeduplicator) -> list[str]:
        """Process Gemini tool definitions and return list of tool IDs.

        Gemini tools format:
        tools: [
            {
                "function_declarations": [
                    {"name": "...", "description": "...", "parameters": {...}}
                ]
            }
        ]
        """
        if not tools:
            return []

        tool_ids = []
        for tool in tools:
            # Gemini wraps functions in function_declarations
            declarations = tool.get("function_declarations", [])
            for decl in declarations:
                name = decl.get("name", "")
                description = decl.get("description", "")
                parameters = decl.get("parameters", {})

                tool_id = tool_dedup.get_or_create(name, description, parameters)
                tool_ids.append(tool_id)

        return tool_ids
