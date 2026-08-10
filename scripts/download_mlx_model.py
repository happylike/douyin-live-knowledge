#!/usr/bin/env python3
"""Download an MLX Whisper repository with curl and resumable large files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default="mlx-community/whisper-large-v3-turbo")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".cache" / "douyin-live-knowledge" / "models" / "whisper-large-v3-turbo",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def fetch_metadata(repo: str, curl: str) -> dict:
    result = subprocess.run(
        [curl, "-fsSL", f"https://huggingface.co/api/models/{quote(repo, safe='/')}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def repository_files(metadata: dict) -> list[str]:
    files = []
    for sibling in metadata.get("siblings", []):
        name = sibling.get("rfilename", "")
        if name and "/" not in name and name not in {".gitattributes"}:
            files.append(name)
    return sorted(files)


def main() -> int:
    args = parse_args()
    curl = shutil.which("curl")
    if not curl:
        print("ERROR: curl is required for resumable model downloads", file=sys.stderr)
        return 2
    if args.dry_run:
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "outputDir": str(args.output_dir.expanduser()),
                    "metadataUrl": f"https://huggingface.co/api/models/{args.repo}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    metadata = fetch_metadata(args.repo, curl)
    files = repository_files(metadata)
    if "config.json" not in files or not any(name.startswith("weights.") for name in files):
        print("ERROR: repository does not look like an MLX Whisper model", file=sys.stderr)
        return 2
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in files:
        url = f"https://huggingface.co/{args.repo}/resolve/main/{quote(name)}?download=true"
        subprocess.run(
            [curl, "-L", "--fail", "--retry", "3", "--continue-at", "-", url, "-o", str(output / name)],
            check=True,
        )
    print(json.dumps({"repo": args.repo, "modelDir": str(output), "files": files}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

