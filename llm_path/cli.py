"""Command-line interface for LLM Path."""

import argparse
import logging

import uvicorn

from .cook import cook_traces
from .proxy import DEFAULT_TARGET_URL, create_app
from .storage import JSONLStorage


def run_proxy(args: argparse.Namespace) -> None:
    """Run the proxy server."""
    # Create storage and app
    storage = JSONLStorage(args.output)
    app = create_app(args.target, storage)

    print("Starting LLM Path proxy server...")
    print(f"  Listening on: http://{args.host}:{args.port}")
    print(f"  Target API:   {args.target}")
    print(f"  Output file:  {args.output}")
    print()

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def run_cook(args: argparse.Namespace) -> None:
    """Run the trace preprocessing."""
    cook_traces(args.input, args.output, args.format)


def main():
    """Main entry point for the CLI."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="LLM Path - Proxy server for tracing LLM requests"
    )
    subparsers = parser.add_subparsers(dest="command")

    # proxy subcommand
    proxy_parser = subparsers.add_parser(
        "proxy", help="Start the proxy server to trace LLM requests"
    )
    proxy_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    proxy_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    proxy_parser.add_argument(
        "--output",
        type=str,
        default="./traces/trace.jsonl",
        help="Output JSONL file path (default: ./traces/trace.jsonl)",
    )
    proxy_parser.add_argument(
        "--target",
        type=str,
        default=DEFAULT_TARGET_URL,
        help=f"Target API URL (default: {DEFAULT_TARGET_URL})",
    )

    # cook subcommand (new functionality)
    cook_parser = subparsers.add_parser(
        "cook", help="Preprocess JSONL traces to visualization-ready JSON"
    )
    cook_parser.add_argument(
        "input",
        help="Input JSONL/JSON file path",
    )
    cook_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./output.json",
        help="Output JSON file path (default: ./output.json)",
    )
    cook_parser.add_argument(
        "--format",
        type=str,
        choices=["auto", "openai", "claude"],
        default="auto",
        help="API format of input traces: auto (default), openai, or claude",
    )

    args = parser.parse_args()

    if args.command == "proxy":
        run_proxy(args)
    elif args.command == "cook":
        run_cook(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
