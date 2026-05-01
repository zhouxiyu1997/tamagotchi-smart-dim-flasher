from __future__ import annotations

import os
import socket
import threading
import webbrowser

from .app import create_app


def pick_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
        return port
    raise RuntimeError(f"Could not find an available port starting at {preferred_port}.")


def main() -> None:
    host = os.environ.get("DIM_HOST", "127.0.0.1")
    requested_port = int(os.environ.get("DIM_PORT", "8765"))
    port = pick_port(host, requested_port)
    url = f"http://{host}:{port}"

    print(f"DiM tool web UI: {url}")

    if os.environ.get("DIM_OPEN_BROWSER", "1") == "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
