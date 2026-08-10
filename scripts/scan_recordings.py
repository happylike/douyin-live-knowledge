#!/usr/bin/env python3
"""Discover split recordings, choose non-destructive format fallbacks, and group reconnects."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


NAME_RE = re.compile(
    r"^(?P<host>.+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2}-\d{2})_(?P<part>\d{3})\.(?P<ext>mp4|ts)$",
    re.IGNORECASE,
)
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
SHANGHAI = timezone(timedelta(hours=8))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reconnect-gap-minutes", type=float, default=12.0)
    parser.add_argument("--ffmpeg", default=os.getenv("FFMPEG_BIN", ""))
    return parser.parse_args()


def parse_recording(path: Path) -> dict[str, Any] | None:
    match = NAME_RE.match(path.name)
    if not match:
        return None
    values = match.groupdict()
    started = datetime.strptime(f"{values['date']} {values['time']}", "%Y-%m-%d %H-%M-%S").replace(tzinfo=SHANGHAI)
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "stemKey": path.name.rsplit(".", 1)[0],
        "host": values["host"],
        "runStartedAt": started.isoformat(),
        "part": int(values["part"]),
        "extension": values["ext"].lower(),
        "sizeBytes": path.stat().st_size,
    }


def locate_ffmpeg(configured: str) -> str | None:
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def probe_duration(path: str, ffmpeg: str | None) -> float | None:
    if not ffmpeg:
        return None
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path],
        text=True,
        capture_output=True,
        check=False,
    )
    match = DURATION_RE.search(result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def choose_variants(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["stemKey"]].append(record)
    selected: list[dict[str, Any]] = []
    alternatives: list[dict[str, Any]] = []
    for key in sorted(grouped):
        candidates = sorted(grouped[key], key=lambda item: (item["extension"] != "mp4", -item["sizeBytes"]))
        chosen = candidates[0]
        chosen["selectedReason"] = "prefer-nonempty-mp4" if chosen["extension"] == "mp4" else "ts-fallback"
        selected.append(chosen)
        for candidate in candidates[1:]:
            alternatives.append({**candidate, "alternativeTo": chosen["path"]})
    return selected, alternatives


def build_runs(records: list[dict[str, Any]], ffmpeg: str | None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["host"], record["runStartedAt"])].append(record)
    runs: list[dict[str, Any]] = []
    for (host, started_at), parts in grouped.items():
        parts.sort(key=lambda item: item["part"])
        total = 0.0
        estimated = False
        for part in parts:
            duration = probe_duration(part["path"], ffmpeg)
            if duration is None:
                duration = 1800.0
                estimated = True
            part["durationSeconds"] = round(duration, 3)
            part["sessionOffsetSeconds"] = round(total, 3)
            total += duration
        start = datetime.fromisoformat(started_at)
        runs.append(
            {
                "host": host,
                "startedAt": started_at,
                "endedAt": (start + timedelta(seconds=total)).isoformat(),
                "durationSeconds": round(total, 3),
                "durationEstimated": estimated,
                "files": parts,
            }
        )
    return sorted(runs, key=lambda item: (item["host"], item["startedAt"]))


def merge_runs(runs: list[dict[str, Any]], gap_minutes: float) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for run in runs:
        previous = sessions[-1] if sessions else None
        can_merge = False
        if previous and previous["host"] == run["host"]:
            gap = datetime.fromisoformat(run["startedAt"]) - datetime.fromisoformat(previous["endedAt"])
            can_merge = timedelta(minutes=-2) <= gap <= timedelta(minutes=gap_minutes)
        if can_merge:
            base_offset = previous["durationSeconds"]
            for part in run["files"]:
                part["sessionOffsetSeconds"] = round(part["sessionOffsetSeconds"] + base_offset, 3)
            previous["runs"].append(run)
            previous["files"].extend(run["files"])
            previous["endedAt"] = run["endedAt"]
            previous["durationSeconds"] = round(previous["durationSeconds"] + run["durationSeconds"], 3)
            previous["durationEstimated"] = previous["durationEstimated"] or run["durationEstimated"]
        else:
            start = datetime.fromisoformat(run["startedAt"])
            sessions.append(
                {
                    "sessionId": f"{run['host']}-{start:%Y%m%d-%H%M%S}",
                    "host": run["host"],
                    "startedAt": run["startedAt"],
                    "endedAt": run["endedAt"],
                    "durationSeconds": run["durationSeconds"],
                    "durationEstimated": run["durationEstimated"],
                    "runs": [run],
                    "files": list(run["files"]),
                }
            )
    return sessions


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: directory not found: {root}", file=sys.stderr)
        return 2
    parsed = [item for path in root.rglob("*") if path.is_file() and (item := parse_recording(path))]
    selected, alternatives = choose_variants(parsed)
    ffmpeg = locate_ffmpeg(args.ffmpeg)
    runs = build_runs(selected, ffmpeg)
    payload = {
        "schemaVersion": 1,
        "root": str(root),
        "ffmpeg": ffmpeg,
        "selectedFileCount": len(selected),
        "alternativeFileCount": len(alternatives),
        "sessions": merge_runs(runs, args.reconnect_gap_minutes),
        "alternatives": alternatives,
    }
    args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.expanduser().resolve().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sessions": len(payload["sessions"]), "selected": len(selected), "alternatives": len(alternatives), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

