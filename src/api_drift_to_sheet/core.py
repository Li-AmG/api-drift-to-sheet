"""Compare JSON record shapes and export selected fields as CSV."""

import csv
import io
import json
from pathlib import Path
from typing import Any


class DataError(ValueError):
    """Input or mapping cannot be safely exported."""


def load_records(path: Path, root: str | None = None) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError(f"Could not read JSON from {path}: {exc}") from exc
    if root:
        for part in root.split("."):
            if not isinstance(data, dict) or part not in data:
                raise DataError(f"Root path {root!r} is missing in {path}")
            data = data[part]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
        raise DataError(f"{path} must contain a nonempty object or array of objects")
    return data


def flatten(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in record.items():
        if not isinstance(key, str) or not key or "." in key:
            raise DataError(f"Field name {key!r} cannot be represented as a dotted path")
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            result.update(flatten(value, path))
        elif isinstance(value, dict):
            result[path] = value
        else:
            result[path] = value
    return result


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def profile(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for record in records:
        for path, value in flatten(record).items():
            entry = observed.setdefault(path, {"types": set(), "present": 0})
            entry["types"].add(value_type(value))
            entry["present"] += 1
    return observed


def compare(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, str]]:
    old, new = profile(before), profile(after)
    changes: list[dict[str, str]] = []
    for path in sorted(old.keys() | new.keys()):
        previous, current = old.get(path), new.get(path)
        if previous is None:
            kind = "added"
        elif current is None:
            kind = "removed"
        elif previous["types"] != current["types"]:
            kind = "type_changed"
        elif previous["present"] == len(before) and current["present"] < len(after):
            kind = "became_optional"
        elif previous["present"] < len(before) and current["present"] == len(after):
            kind = "became_required"
        else:
            continue
        changes.append({
            "field": path,
            "change": kind,
            "before_types": ",".join(sorted(previous["types"])) if previous else "",
            "after_types": ",".join(sorted(current["types"])) if current else "",
            "before_present": f"{previous['present']}/{len(before)}" if previous else "0",
            "after_present": f"{current['present']}/{len(after)}" if current else "0",
        })
    return changes


def load_mapping(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError(f"Could not read mapping from {path}: {exc}") from exc
    if not isinstance(data, dict) or not data or not all(
        isinstance(column, str) and column and isinstance(field, str) and field
        for column, field in data.items()
    ):
        raise DataError("Mapping must be a nonempty object of CSV column names to dotted JSON paths")
    if any(column.lstrip().startswith(("=", "+", "-", "@")) for column in data):
        raise DataError("CSV column names cannot start with spreadsheet formula characters")
    return data


def export_csv(records: list[dict[str, Any]], mapping: dict[str, str]) -> str:
    if any(column.lstrip().startswith(("=", "+", "-", "@")) for column in mapping):
        raise DataError("CSV column names cannot start with spreadsheet formula characters")
    rows = [flatten(record) for record in records]
    missing = sorted(set(mapping.values()) - set().union(*(row.keys() for row in rows)))
    if missing:
        raise DataError("Mapped fields are absent from every record: " + ", ".join(missing))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(mapping), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        exported: dict[str, str] = {}
        for column, path in mapping.items():
            value = row.get(path)
            if isinstance(value, (dict, list)):
                exported[column] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            elif value is None:
                exported[column] = ""
            else:
                exported[column] = str(value)
            # CSV quoting alone does not stop spreadsheet formula evaluation.
            if isinstance(value, str) and exported[column].lstrip().startswith(("=", "+", "-", "@")):
                exported[column] = "'" + exported[column]
        writer.writerow(exported)
    return out.getvalue()
