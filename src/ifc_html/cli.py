from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .core import ViewerOptions, convert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create one fully offline HTML viewer from one or more IFC files."
    )
    parser.add_argument("ifc", nargs="+", type=Path, help="One or more IFC input files")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output HTML file")
    parser.add_argument("--title", default="Free HTML Model Viewer", help="Viewer title")
    parser.add_argument("--prepared-by", default="", help="Optional prepared-by name")
    parser.add_argument(
        "--flight-speed",
        type=float,
        default=5.0,
        help="Initial WASD flight speed from 0.5 to 50.0 (default: 5.0)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    try:
        result = convert(
            args.ifc,
            args.output,
            options=ViewerOptions(
                title=args.title,
                prepared_by=args.prepared_by,
                flight_speed=args.flight_speed,
            ),
            progress=(lambda message: print(message)) if args.verbose else None,
        )
    except Exception as error:
        parser.exit(1, f"Error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
