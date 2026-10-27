"""An explicit acquisition step, offline analysis, and local static preview."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .acquire import RESOURCE_DIR, acquire
from .export import export_study
from .server import make_server


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Historical Sentinel-2 candidate-water change study."
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser(
        "acquire", help="Fetch only pinned historical image crop byte ranges."
    )
    download.add_argument("--output", type=Path, required=True)
    analyze = sub.add_parser(
        "analyze", help="Analyze two local six-band projected GeoTIFFs offline."
    )
    analyze.add_argument("--before", type=Path, required=True)
    analyze.add_argument("--after", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    demo = sub.add_parser("demo", help="Run the bundled historical crop with no external network.")
    demo.add_argument("--output", type=Path, required=True)
    serve = sub.add_parser("serve", help="Preview an existing export on127.0.0.1.")
    serve.add_argument("--directory", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)
    try:
        if args.command == "acquire":
            print(json.dumps(acquire(args.output), indent=2))
        elif args.command == "serve":
            with make_server(args.directory, args.port) as server:
                print(f"Preview: http://127.0.0.1:{server.server_port}/", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
        else:
            if args.command == "demo":
                before, after = (
                    RESOURCE_DIR / "study" / "before.tif",
                    RESOURCE_DIR / "study" / "after.tif",
                )
            else:
                before, after = args.before, args.after
            report = export_study(before, after, args.output)
            print(f"Report: {args.output / 'index.html'}")
            if "thresholds" in report:
                baseline = report["thresholds"][1]
                print(
                    f"Candidate gain: {baseline['gain_km2']:.3f} km²; loss: {baseline['loss_km2']:.3f} km²"
                )
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
