"""Command-line interface."""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from .core import DataError, compare, export_csv, load_mapping, load_records


def write_new(path: Path, text: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(text)
    except FileExistsError as exc:
        raise DataError(f"Refusing to overwrite {path}") from exc
    except OSError as exc:
        raise DataError(f"Could not write {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check API JSON drift and export mapped CSV locally")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="compare two JSON samples")
    check.add_argument("before", type=Path)
    check.add_argument("after", type=Path)
    check.add_argument("--root", help="dotted path to records array, e.g. data.items")
    check.add_argument("--json", action="store_true", help="print machine-readable report")
    check.add_argument("--out", type=Path, help="save report to a new file")
    export = commands.add_parser("export", help="export JSON records to mapped CSV")
    export.add_argument("input", type=Path)
    export.add_argument("mapping", type=Path, help="JSON object mapping column names to dotted paths")
    export.add_argument("output", type=Path)
    export.add_argument("--root", help="dotted path to records array")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            changes = compare(load_records(args.before, args.root), load_records(args.after, args.root))
            if args.json:
                text = json.dumps(changes, indent=2, ensure_ascii=False) + "\n"
            else:
                stream = io.StringIO(newline="")
                columns = ["field", "change", "before_types", "after_types", "before_present", "after_present"]
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(changes)
                text = stream.getvalue()
            if args.out:
                write_new(args.out, text)
            else:
                sys.stdout.write(text)
            return 2 if changes else 0
        csv_text = export_csv(load_records(args.input, args.root), load_mapping(args.mapping))
        write_new(args.output, csv_text)
        return 0
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
