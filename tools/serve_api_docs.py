#!/usr/bin/env python3
"""Serve the OpenAPI and AsyncAPI documentation on localhost."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8082)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Порт должен быть в диапазоне 1..65535.")

    docs = Path(__file__).resolve().parents[1] / "docs/api"
    handler = partial(SimpleHTTPRequestHandler, directory=str(docs))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Документация API: http://127.0.0.1:{args.port}/", flush=True)
        print("Ctrl+C — остановить сервер документации.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
