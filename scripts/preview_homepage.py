"""Loopback-only static homepage preview; gzip mirrors the audit delivery assumptions."""

import gzip
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.chdir(Path(__file__).resolve().parents[1] / "frontend")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def send_head(self):
        path = Path(self.translate_path(self.path.split("?")[0]))
        if path.is_dir():
            path = path / "index.html"
        if (
            path.is_file()
            and any(
                str(path).endswith(ext)
                for ext in (
                    ".html",
                    ".css",
                    ".js",
                    ".json",
                    ".topojson",
                    ".svg",
                    ".csv",
                )
            )
            and "gzip" in self.headers.get("Accept-Encoding", "")
        ):
            import io

            content = gzip.compress(path.read_bytes(), mtime=0)
            self.send_response(200)
            self.send_header("Content-type", self.guess_type(str(path)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            return io.BytesIO(content)
        return super().send_head()


ThreadingHTTPServer(("127.0.0.1", 8769), Handler).serve_forever()
