#!/usr/bin/env python3
"""Create an isolated transcription runtime for this skill."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


def default_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "faster-whisper"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("auto", "mlx", "faster-whisper"), default="auto")
    parser.add_argument(
        "--venv-dir",
        type=Path,
        default=Path.home() / ".cache" / "douyin-live-knowledge" / "venv",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--index-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")


def commands(args: argparse.Namespace) -> tuple[str, list[list[str]]]:
    backend = default_backend() if args.backend == "auto" else args.backend
    python = venv_python(args.venv_dir)
    packages = ["imageio-ffmpeg"]
    packages.append("mlx-whisper" if backend == "mlx" else "faster-whisper")
    pip_command = [str(python), "-m", "pip", "install", "--upgrade"]
    if args.index_url:
        pip_command.extend(["--index-url", args.index_url])
    pip_command.extend(packages)
    return backend, [
        [args.python, "-m", "venv", str(args.venv_dir)],
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        pip_command,
    ]


def main() -> int:
    args = parse_args()
    backend, steps = commands(args)
    if args.dry_run:
        print(json.dumps({"backend": backend, "commands": steps}, ensure_ascii=False, indent=2))
        return 0
    args.venv_dir.expanduser().parent.mkdir(parents=True, exist_ok=True)
    for command in steps:
        subprocess.run(command, check=True)
    python = venv_python(args.venv_dir)
    verify = [str(python), "-c"]
    if backend == "mlx":
        verify.append("import imageio_ffmpeg, mlx_whisper; print(imageio_ffmpeg.get_ffmpeg_exe())")
    else:
        verify.append("import imageio_ffmpeg, faster_whisper; print(imageio_ffmpeg.get_ffmpeg_exe())")
    result = subprocess.run(verify, check=True, text=True, capture_output=True)
    print(
        json.dumps(
            {
                "backend": backend,
                "venvPython": str(python),
                "ffmpeg": result.stdout.strip(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

