#!/usr/bin/env python3
"""Serve the standalone site without letting retired text sidecars mask updates."""
import argparse
import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".mjs": "text/javascript"}

    def send_head(self):
        path = self.translate_path(self.path)
        accepted = self.headers.get("Accept-Encoding", "")
        if os.path.isfile(path) and Path(path).suffix in {".wasm", ".whl", ".zip"}:
            for encoding, suffix in (("br", ".br"), ("gzip", ".gz")):
                # Respect clients that explicitly disable an encoding.
                encodings = [entry.strip() for entry in accepted.split(",")]
                available = any(entry.split(";")[0].strip() == encoding and not any(
                    param.strip().startswith("q=") and float(param.strip()[2:]) == 0
                    for param in entry.split(";")[1:]
                ) for entry in encodings)
                if available and os.path.isfile(path + suffix):
                    file = open(path + suffix, "rb")
                    self.send_response(200)
                    self.send_header("Content-Type", self.guess_type(path))
                    self.send_header("Content-Encoding", encoding)
                    self.send_header("Vary", "Accept-Encoding")
                    self.send_header("Content-Length", str(os.fstat(file.fileno()).st_size))
                    self.end_headers()
                    return file
        return super().send_head()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / "dist"
    server = ThreadingHTTPServer((args.bind, args.port), functools.partial(Handler, directory=str(directory)))
    print(f"HEPkit preview: http://localhost:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
