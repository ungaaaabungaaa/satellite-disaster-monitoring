"""Exercise only an installed wheel from a temporary directory outside the source tree."""

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    wheel = Path(sys.argv[1]).resolve(strict=True)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        required = {
            "satellite_monitoring/resources/source-pins.json",
            "satellite_monitoring/resources/provenance/before-item.json",
            "satellite_monitoring/resources/provenance/after-item.json",
            "satellite_monitoring/resources/study/before.tif",
            "satellite_monitoring/resources/study/after.tif",
            "satellite_monitoring/resources/study/acquisition.json",
            *{
                f"satellite_monitoring/resources/viewer/{name}"
                for name in ["index.html", "style.css", "app.js", "classification.mjs"]
            },
        }
        assert required <= set(names), "Runtime assets are missing from the wheel"
        assert sum(item.file_size for item in archive.infolist()) < 20_000_000
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
    with tempfile.TemporaryDirectory(prefix="satellite-wheel-") as temporary:
        root = Path(temporary)
        target = root / "installed"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-compile",
                "--target",
                str(target),
                str(wheel),
            ],
            check=True,
            cwd=root,
        )
        environment = {**os.environ, "PYTHONPATH": str(target)}
        probe = r"""
import json
import socket
from pathlib import Path
from threading import Thread
from urllib.request import urlopen
from unittest.mock import patch
import satellite_monitoring
from satellite_monitoring.acquire import RESOURCE_DIR
from satellite_monitoring.cli import main
from satellite_monitoring.server import make_server

assert Path(satellite_monitoring.__file__).resolve().is_relative_to(Path("installed").resolve())
with patch.object(socket, "create_connection", side_effect=AssertionError("Offline demo attempted network")):
    assert main(["demo", "--output", "report"]) == 0
    assert main(["analyze", "--before", str(RESOURCE_DIR / "study/before.tif"),
                 "--after", str(RESOURCE_DIR / "study/after.tif"), "--output", "analysis"]) == 0
report = Path("report")
metrics = json.loads((report / "metrics.json").read_text())
assert metrics["study_status"] == "pinned-historical-study"
default = metrics["thresholds"][1]
assert default["common_valid_pixels"] == 427550
assert default["gain_pixels"] == 259207
assert default["loss_pixels"] == 7262
assert json.loads(Path("analysis/metrics.json").read_text())["thresholds"] == metrics["thresholds"]
with make_server(report, 0) as server:
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for filename in ["index.html", "app.js", "classification.mjs", "before.f32.gz", "change.tif"]:
            with urlopen(base + "/" + filename, timeout=5) as response:
                assert response.status == 200
                assert response.read()
    finally:
        server.shutdown()
        thread.join(timeout=5)
print("Installed wheel: real offline study, explicit analysis, resources, and preview passed.")
"""
        subprocess.run([sys.executable, "-c", probe], env=environment, cwd=root, check=True)
        subprocess.run(
            [sys.executable, "-m", "satellite_monitoring", "--version"],
            env=environment,
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    main()
