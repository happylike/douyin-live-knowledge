#!/usr/bin/env python3
"""Validate structured live-stream analysis before Obsidian rendering."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TIME_RE = re.compile(r"^(?:\d{2}:)?\d{2}:\d{2}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    return parser.parse_args()


def to_seconds(value: str) -> int | None:
    if not TIME_RE.match(value):
        return None
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    session = data.get("session")
    if not isinstance(session, dict):
        errors.append("session must be an object")
    else:
        for key in ("sessionId", "host", "title", "overview", "sourceFiles"):
            if key not in session:
                errors.append(f"session.{key} is required")
    seen: set[str] = set()
    all_ids: set[str] = set()
    for collection, id_key in (("cases", "caseId"), ("knowledge", "knowledgeId"), ("valuableChat", "chatId")):
        values = data.get(collection, [])
        if not isinstance(values, list):
            errors.append(f"{collection} must be a list")
            continue
        for index, item in enumerate(values):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            item_id = item.get(id_key)
            if not isinstance(item_id, str) or not item_id:
                errors.append(f"{prefix}.{id_key} is required")
            elif item_id in seen:
                errors.append(f"duplicate id: {item_id}")
            else:
                seen.add(item_id)
                all_ids.add(item_id)
            importance = item.get("importance")
            if not isinstance(importance, int) or not 1 <= importance <= 5:
                errors.append(f"{prefix}.importance must be an integer from 1 to 5")
    for index, item in enumerate(data.get("cases", [])):
        prefix = f"cases[{index}]"
        if item.get("answerStatus") not in {"none", "partial", "substantive"}:
            errors.append(f"{prefix}.answerStatus must be none, partial, or substantive")
        if not isinstance(item.get("hasDeadlineRisk"), bool):
            errors.append(f"{prefix}.hasDeadlineRisk must be boolean")
        ranges = item.get("sourceRanges")
        if not isinstance(ranges, list) or not ranges:
            errors.append(f"{prefix}.sourceRanges must be a non-empty list")
            continue
        for range_index, value in enumerate(ranges):
            start = to_seconds(str(value.get("start", ""))) if isinstance(value, dict) else None
            end = to_seconds(str(value.get("end", ""))) if isinstance(value, dict) else None
            if start is None or end is None or end <= start:
                errors.append(f"{prefix}.sourceRanges[{range_index}] has invalid timestamps")
            if isinstance(value, dict) and not value.get("sourceFile"):
                errors.append(f"{prefix}.sourceRanges[{range_index}].sourceFile is required")
    previous_end = 0
    for index, item in enumerate(data.get("timeline", [])):
        start = to_seconds(str(item.get("start", ""))) if isinstance(item, dict) else None
        end = to_seconds(str(item.get("end", ""))) if isinstance(item, dict) else None
        if start is None or end is None or end <= start:
            errors.append(f"timeline[{index}] has invalid timestamps")
            continue
        if start < previous_end:
            errors.append(f"timeline[{index}] overlaps the previous entry")
        elif start > previous_end:
            warnings.append(f"timeline gap before entry {index}: {previous_end}s to {start}s")
        previous_end = end
        for linked_id in item.get("linkedIds", []):
            if linked_id not in all_ids:
                errors.append(f"timeline[{index}] links unknown id: {linked_id}")
    return errors, warnings


def main() -> int:
    args = parse_args()
    try:
        data = json.loads(args.analysis.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    errors, warnings = validate(data)
    print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

