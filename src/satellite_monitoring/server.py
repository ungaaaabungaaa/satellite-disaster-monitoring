"""Loopback-only, read-only access to known exported viewer files."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

FILES = {
    "index.html",
    "style.css",
    "app.js",
    "classification.mjs",
    "data.json",
    "metrics.json",
    "before.png",
    "after.png",
    "before.f32.gz",
    "after.f32.gz",
    "change.tif",
    "change.png",
    "footprint.geojson",
}


def make_server(directory: Path, port=8790):
    root = directory.resolve(strict=True)
    if not (root / "index.html").is_file() or not 0 <= port <= 65535:
        raise ValueError("Select an exported viewer directory and a port from0to65535.")

    class Handler(SimpleHTTPRequestHandler):
        def allowed(self):
            hosts = self.headers.get_all("Host", [])
            port = self.server.server_port
            expected = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if port == 80:
                expected.update({"127.0.0.1", "localhost"})
            if len(hosts) != 1 or hosts[0].strip().lower() not in expected:
                self.send_error(403, "Unrecognized local preview Host.")
                return False
            path = unquote(urlsplit(self.path).path)
            name = "index.html" if path == "/" else path.removeprefix("/")
            target = root / name
            if (
                name not in FILES
                or not target.is_file()
                or target.is_symlink()
                or not target.resolve().is_relative_to(root)
            ):
                self.send_error(404, "Not an exported study asset.")
                return False
            self.path = "/" + name
            return True

        def do_GET(self):
            if self.allowed():
                super().do_GET()

        def do_HEAD(self):
            if self.allowed():
                super().do_HEAD()

        def end_headers(self):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(root)))
