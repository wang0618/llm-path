"""Command-line interface for LLM Trace."""

import argparse
import logging

import uvicorn

from .proxy import DEFAULT_TARGET_URL, create_app
from .storage import JSONLStorage


def main():
    """Main entry point for the CLI."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="LLM Trace - Proxy server for tracing LLM requests"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./traces/trace.jsonl",
        help="Output JSONL file path (default: ./traces/trace.jsonl)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=DEFAULT_TARGET_URL,
        help=f"Target API URL (default: {DEFAULT_TARGET_URL})",
    )

    args = parser.parse_args()

    # Create storage and app
    storage = JSONLStorage(args.output)
    app = create_app(args.target, storage)

    print("Starting LLM Trace proxy server...")
    print(f"  Listening on: http://{args.host}:{args.port}")
    print(f"  Target API:   {args.target}")
    print(f"  Output file:  {args.output}")
    print()

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
