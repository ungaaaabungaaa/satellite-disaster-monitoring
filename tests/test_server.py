import os
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from satellite_monitoring.server import make_server


class ServerTests(unittest.TestCase):
    def test_loopback_readonly_whitelist_and_host_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "site").mkdir()
            site = root / "site"
            (site / "index.html").write_text("<main>Exported study</main>")
            (site / "threshold-sensitivity.tif").write_bytes(b"sensitivity fixture")
            (root / "private.txt").write_text("must not be served")
            with make_server(site, 0) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    with urlopen(base + "/", timeout=5) as response:
                        self.assertIn(b"Exported study", response.read())
                        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                        self.assertIn(
                            "default-src 'self'", response.headers["Content-Security-Policy"]
                        )
                    with urlopen(base + "/threshold-sensitivity.tif", timeout=5) as response:
                        self.assertEqual(response.read(), b"sensitivity fixture")
                    for path in [
                        "/../private.txt",
                        "/private.txt",
                        "/other/",
                        "/%2e%2e/private.txt",
                    ]:
                        with self.assertRaises(HTTPError) as error:
                            urlopen(base + path, timeout=5)
                        self.assertEqual(error.exception.code, 404)
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base + "/", data=b"write"), timeout=5)
                    self.assertEqual(error.exception.code, 501)
                    with self.assertRaises(HTTPError) as error:
                        urlopen(
                            Request(base + "/", headers={"Host": "attacker.example"}), timeout=5
                        )
                    self.assertEqual(error.exception.code, 403)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)

    @unittest.skipIf(os.name == "nt", "Creating symlinks requires Windows developer privileges")
    def test_allowlisted_name_cannot_follow_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text("<main>Study</main>")
            private = root / "private.png"
            private.write_bytes(b"private location data")
            (site / "before.png").symlink_to(private)
            with make_server(site, 0) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with self.assertRaises(HTTPError) as error:
                        urlopen(f"http://127.0.0.1:{server.server_port}/before.png", timeout=5)
                    self.assertEqual(error.exception.code, 404)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)

    def test_missing_export_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                make_server(Path(d), 0)


if __name__ == "__main__":
    unittest.main()
