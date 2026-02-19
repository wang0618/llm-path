"""Proxy server for intercepting LLM API requests."""

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .models import TraceRecord
from .storage import JSONLStorage

# Default OpenAI API base URL
DEFAULT_TARGET_URL = "https://api.openai.com"


class LLMProxy:
    """Proxy server that intercepts and logs LLM API requests."""

    def __init__(self, target_url: str, storage: JSONLStorage):
        self.target_url = target_url.rstrip("/")
        self.storage = storage
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def proxy_request(self, request: Request) -> Response:
        """Proxy any request to the target API."""
        start_time = time.time()

        # Get the full path from request
        path = request.url.path
        query_string = request.url.query
        upstream_url = f"{self.target_url}{path}"
        if query_string:
            upstream_url = f"{upstream_url}?{query_string}"

        # Read and parse request body
        body = await request.body()
        request_data = None
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                # Not JSON, forward as raw body
                pass

        # Build headers for upstream request (forward most headers)
        headers = {}
        for key, value in request.headers.items():
            # Skip hop-by-hop headers
            if key.lower() not in ("host", "connection", "keep-alive", "transfer-encoding"):
                headers[key] = value

        # Determine if streaming (only for JSON requests with stream=true)
        is_stream = request_data.get("stream", False) if isinstance(request_data, dict) else False

        if is_stream:
            return await self._handle_streaming_request(
                upstream_url, headers, request_data, start_time
            )
        else:
            return await self._handle_normal_request(
                request.method, upstream_url, headers, request_data, body, start_time
            )

    async def _handle_normal_request(
        self,
        method: str,
        url: str,
        headers: dict,
        request_data: dict | None,
        raw_body: bytes,
        start_time: float,
    ) -> Response:
        """Handle non-streaming request."""
        # Only trace POST requests with JSON body (likely LLM calls)
        should_trace = method == "POST" and request_data is not None

        record = TraceRecord(request=request_data) if should_trace else None

        if record:
            logging.info("Record non-stream LLM Call")

        try:
            # Use JSON body if available, otherwise raw body
            if request_data is not None:
                response = await self.client.request(
                    method, url, headers=headers, json=request_data
                )
            else:
                response = await self.client.request(
                    method, url, headers=headers, content=raw_body
                )

            duration_ms = int((time.time() - start_time) * 1000)

            # Try to parse response as JSON
            try:
                response_data = response.json()
                if record:
                    record.response = response_data
                    record.duration_ms = duration_ms
                    self.storage.append(record)
                return JSONResponse(response_data, status_code=response.status_code)
            except json.JSONDecodeError:
                # Return raw response
                if record:
                    record.response = {"raw": response.text}
                    record.duration_ms = duration_ms
                    self.storage.append(record)
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )

        except httpx.RequestError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if record:
                record.error = str(e)
                record.duration_ms = duration_ms
                self.storage.append(record)

            return JSONResponse(
                {"error": {"message": str(e), "type": "proxy_error"}},
                status_code=502,
            )

    async def _handle_streaming_request(
        self,
        url: str,
        headers: dict,
        request_data: dict,
        start_time: float,
    ) -> Response:
        """Handle streaming request."""
        record = TraceRecord(request=request_data)

        logging.info("Record stream LLM Call")

        async def generate() -> AsyncIterator[bytes]:
            chunks: list[str] = []
            collected_content = ""
            response_id = None
            model = None

            try:
                async with self.client.stream(
                    "POST", url, headers=headers, json=request_data
                ) as response:
                    async for line in response.aiter_lines():
                        # Forward raw line to client
                        yield f"{line}\n".encode("utf-8")

                        # Parse SSE data
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                continue

                            try:
                                chunk = json.loads(data)
                                chunks.append(data)

                                # Extract metadata from first chunk
                                if response_id is None:
                                    response_id = chunk.get("id")
                                    model = chunk.get("model")

                                # Extract content delta
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        collected_content += content

                            except json.JSONDecodeError:
                                pass

                # Record the complete response
                duration_ms = int((time.time() - start_time) * 1000)
                record.duration_ms = duration_ms
                record.response = {
                    "id": response_id,
                    "model": model,
                    "content": collected_content,
                    "stream": True,
                }
                self.storage.append(record)

            except httpx.RequestError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                record.error = str(e)
                record.duration_ms = duration_ms
                self.storage.append(record)

                error_response = json.dumps(
                    {"error": {"message": str(e), "type": "proxy_error"}}
                )
                yield f"data: {error_response}\n".encode("utf-8")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )


def create_app(target_url: str, storage: JSONLStorage) -> Starlette:
    """Create the Starlette application."""
    proxy = LLMProxy(target_url, storage)

    async def proxy_all(request: Request) -> Response:
        return await proxy.proxy_request(request)

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def on_shutdown():
        await proxy.close()

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            # Catch-all route for all other paths
            Route("/{path:path}", proxy_all, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
        ],
        on_shutdown=[on_shutdown],
    )

    return app
