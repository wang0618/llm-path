"""Viewer server for trace visualization."""

import json
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ._version import __version__
from .cook import TraceCooker

APP_NAME = "llm-path"
DEFAULT_PORT = 8765
MAX_PORT_ATTEMPTS = 10


def get_viewer_dist_path() -> Path:
    """Get the path to bundled viewer dist directory."""
    return Path(__file__).parent / "viewer_dist"


def load_and_cook_file(file_path: str) -> dict:
    """Load a trace file and cook it if needed.

    Args:
        file_path: Path to the trace file (JSONL or cooked JSON)

    Returns:
        Cooked trace data as dict
    """
    input_file = Path(file_path)

    if not input_file.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = input_file.read_text(encoding="utf-8")

    # Try to parse as JSON first
    try:
        data = json.loads(content)
        # Check if already cooked
        if isinstance(data, dict) and all(k in data for k in ("messages", "tools", "requests")):
            return data
        # Single record or array of records - need to cook
        records = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        # Parse as JSONL
        records = []
        for line in content.strip().split("\n"):
            if line.strip():
                records.append(json.loads(line))

    # Cook the records
    cooker = TraceCooker()
    output = cooker.cook(records)
    return output.to_dict()


def create_viewer_app() -> Starlette:
    """Create the viewer Starlette app."""
    viewer_dist = get_viewer_dist_path()

    async def info_endpoint(request):
        """Return server info for version checking."""
        return JSONResponse(
            {
                "name": APP_NAME,
                "version": __version__,
            }
        )

    async def local_endpoint(request):
        """Load and return trace data from a local file path."""
        file_path = request.query_params.get("path")
        if not file_path:
            return JSONResponse({"error": "Missing 'path' parameter"}, status_code=400)

        try:
            data = load_and_cook_file(file_path)
            return JSONResponse(data)
        except FileNotFoundError as e:
            return JSONResponse({"error": str(e)}, status_code=404)
        except json.JSONDecodeError as e:
            return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    async def index_endpoint(request):
        """Serve index.html for SPA routing."""
        return FileResponse(viewer_dist / "index.html")

    routes = [
        Route("/_info", info_endpoint),
        Route("/_local", local_endpoint),
        Mount("/assets", StaticFiles(directory=viewer_dist / "assets"), name="assets"),
        # Catch-all for SPA routing
        Route("/{path:path}", index_endpoint),
    ]

    return Starlette(routes=routes)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def check_existing_server(port: int, host: str = "127.0.0.1") -> dict | None:
    """Check if an existing llm-path server is running on the port.

    Returns:
        Server info dict if it's our server, None otherwise
    """
    try:
        response = httpx.get(f"http://{host}:{port}/_info", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except (httpx.RequestError, json.JSONDecodeError):
        pass
    return None


def find_available_port(start_port: int, host: str = "127.0.0.1") -> int:
    """Find an available port starting from start_port.

    Args:
        start_port: Port to start searching from
        host: Host to bind to

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found within MAX_PORT_ATTEMPTS
    """
    for offset in range(MAX_PORT_ATTEMPTS):
        port = start_port + offset
        if not is_port_in_use(port, host):
            return port

    raise RuntimeError(
        f"Could not find available port in range {start_port}-{start_port + MAX_PORT_ATTEMPTS - 1}"
    )


def open_browser(url: str) -> None:
    """Open URL in the default browser."""
    # Use subprocess to avoid blocking on some systems
    if sys.platform == "darwin":
        subprocess.Popen(["open", url])
    elif sys.platform == "win32":
        subprocess.Popen(["start", url], shell=True)
    else:
        # Linux and others
        try:
            subprocess.Popen(["xdg-open", url])
        except FileNotFoundError:
            webbrowser.open(url)


def run_viewer(input_path: str, port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> None:
    """Run the viewer server.

    Args:
        input_path: Path to trace file (JSONL or cooked JSON)
        port: Port to listen on (will auto-increment if in use)
        host: Host to bind to
    """
    # Check for bundled viewer
    viewer_dist = get_viewer_dist_path()
    if not viewer_dist.exists():
        print("Error: Viewer assets not found.")
        print("This usually means the package was not built correctly.")
        print("For development, run the viewer separately: cd viewer && npm run dev")
        sys.exit(1)

    # Resolve to absolute path
    abs_path = str(Path(input_path).absolute())

    # Check if existing server can be reused
    if is_port_in_use(port, host):
        server_info = check_existing_server(port, host)
        if server_info:
            if server_info.get("name") == APP_NAME and server_info.get("version") == __version__:
                # Same version server is running, just open browser with local param
                url = f"http://{host}:{port}/?local={abs_path}"
                print(f"Reusing existing server at http://{host}:{port}")
                print(f"Opening: {url}")
                open_browser(url)
                return
            else:
                # Different version or different app
                print(
                    f"Port {port} is in use by {server_info.get('name')} "
                    f"v{server_info.get('version')} (current: v{__version__})"
                )
                port = find_available_port(port + 1, host)
                print(f"Using port {port} instead")
        else:
            # Port in use by unknown service
            print(f"Port {port} is in use by another service")
            port = find_available_port(port + 1, host)
            print(f"Using port {port} instead")

    # Create and run server
    app = create_viewer_app()
    url = f"http://{host}:{port}/?local={abs_path}"

    print(f"Starting viewer server at http://{host}:{port}")
    print(f"File: {abs_path}")
    print()

    # Open browser after a short delay (server needs to start)
    import threading

    def delayed_open():
        import time

        time.sleep(0.5)
        open_browser(url)

    threading.Thread(target=delayed_open, daemon=True).start()

    # Run server (blocking)
    uvicorn.run(app, host=host, port=port, log_level="warning")
