#!/usr/bin/env python3
"""Transcribe local media into timestamped JSON, SRT, Markdown, and text."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_FW_MODEL = "large-v3-turbo"
DEFAULT_LOCAL_MLX_MODEL = (
    Path.home() / ".cache" / "douyin-live-knowledge" / "models" / "whisper-large-v3-turbo"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", choices=("auto", "mlx", "faster-whisper"), default="auto")
    parser.add_argument("--model")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--initial-prompt", default="")
    parser.add_argument("--device", default="auto", help="faster-whisper device")
    parser.add_argument("--compute-type", default="", help="faster-whisper compute type")
    return parser.parse_args()


def choose_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "faster-whisper"


def choose_model(backend: str, requested: str | None) -> str:
    if requested:
        return requested
    if backend != "mlx":
        return DEFAULT_FW_MODEL
    local_model = DEFAULT_LOCAL_MLX_MODEL.expanduser()
    has_config = (local_model / "config.json").is_file()
    has_weights = any(local_model.glob("weights.*"))
    return str(local_model) if has_config and has_weights else DEFAULT_MLX_MODEL


def locate_ffmpeg() -> str:
    configured = os.getenv("FFMPEG_BIN", "").strip()
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError("FFmpeg not found. Install ffmpeg or imageio-ffmpeg.") from exc


def ffmpeg_on_path(ffmpeg: str):
    temp_dir = tempfile.TemporaryDirectory(prefix="douyin-live-ffmpeg-")
    link = Path(temp_dir.name) / "ffmpeg"
    link.symlink_to(Path(ffmpeg).resolve())
    previous = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{temp_dir.name}{os.pathsep}{previous}"
    return temp_dir, previous


def normalize_segments(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        text = " ".join(str(item.get("text", "")).split())
        if not text:
            continue
        segment = {
            "index": len(normalized) + 1,
            "start": round(float(item.get("start", 0.0)), 3),
            "end": round(float(item.get("end", 0.0)), 3),
            "text": text,
        }
        for key in ("avg_logprob", "no_speech_prob", "compression_ratio"):
            value = item.get(key)
            if isinstance(value, (int, float)):
                segment[key] = round(float(value), 6)
        normalized.append(segment)
    return normalized


def transcribe_mlx(media: Path, model: str, language: str, prompt: str) -> tuple[list[dict[str, Any]], str]:
    try:
        import mlx_whisper  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Missing mlx-whisper. Install mlx-whisper and imageio-ffmpeg.") from exc
    ffmpeg = locate_ffmpeg()
    temp_dir, previous_path = ffmpeg_on_path(ffmpeg)
    try:
        result = mlx_whisper.transcribe(
            str(media),
            path_or_hf_repo=model,
            language=language or None,
            initial_prompt=prompt or None,
            condition_on_previous_text=False,
            word_timestamps=False,
            verbose=False,
        )
    finally:
        os.environ["PATH"] = previous_path
        temp_dir.cleanup()
    return normalize_segments(result.get("segments", [])), str(result.get("language", language))


def transcribe_faster(
    media: Path,
    model: str,
    language: str,
    prompt: str,
    device: str,
    compute_type: str,
) -> tuple[list[dict[str, Any]], str]:
    try:
        import ctranslate2  # type: ignore
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Missing faster-whisper. Install faster-whisper.") from exc
    if device == "auto":
        device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
    if not compute_type:
        compute_type = "float16" if device == "cuda" else "int8"
    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    iterator, info = whisper.transcribe(
        str(media),
        language=language or None,
        initial_prompt=prompt or None,
        condition_on_previous_text=False,
        beam_size=5,
        vad_filter=True,
    )
    raw = [
        {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "avg_logprob": segment.avg_logprob,
            "no_speech_prob": segment.no_speech_prob,
            "compression_ratio": segment.compression_ratio,
        }
        for segment in iterator
    ]
    return normalize_segments(raw), str(getattr(info, "language", language))


def timestamp(seconds: float, srt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_outputs(
    output_dir: Path,
    media: Path,
    backend: str,
    model: str,
    language: str,
    segments: list[dict[str, Any]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(item["text"] for item in segments)
    highest_repeat = (max(counts.values()) / len(segments)) if segments else 0.0
    high_no_speech = [item for item in segments if item.get("no_speech_prob", 0) >= 0.6]
    high_no_speech_ratio = len(high_no_speech) / len(segments) if segments else 0.0
    failures = []
    warnings = []
    if highest_repeat >= 0.35:
        failures.append("转写文本高度重复，疑似模型幻觉或音轨异常，禁止直接进入内容分析。")
    if high_no_speech_ratio >= 0.65:
        warnings.append("模型给出较高无语音概率；若文本密度正常可人工抽查后继续。")
    payload = {
        "schemaVersion": 1,
        "sourcePath": str(media),
        "backend": backend,
        "model": model,
        "language": language,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": segments[-1]["end"] if segments else 0,
        "segmentCount": len(segments),
        "quality": {
            "status": "failed" if failures else "review",
            "highestExactRepeatRatio": round(highest_repeat, 6),
            "highNoSpeechRatio": round(high_no_speech_ratio, 6),
            "warnings": failures + warnings,
        },
        "segments": segments,
    }
    json_path = output_dir / "transcript.json"
    srt_path = output_dir / "transcript.srt"
    text_path = output_dir / "transcript.txt"
    md_path = output_dir / "transcript.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    srt_path.write_text(
        "".join(
            f"{item['index']}\n{timestamp(item['start'], True)} --> {timestamp(item['end'], True)}\n{item['text']}\n\n"
            for item in segments
        ),
        encoding="utf-8",
    )
    text_path.write_text("\n".join(item["text"] for item in segments) + "\n", encoding="utf-8")
    md_path.write_text(
        "# 逐字稿\n\n"
        + f"> 来源：`{media.name}`\n> 后端：`{backend}` · 模型：`{model}`\n\n"
        + "\n\n".join(
            f"**[{timestamp(item['start'])}–{timestamp(item['end'])}]** {item['text']}" for item in segments
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "json": str(json_path),
        "srt": str(srt_path),
        "text": str(text_path),
        "markdown": str(md_path),
        "qualityStatus": payload["quality"]["status"],
    }


def main() -> int:
    args = parse_args()
    media = args.media.expanduser().resolve()
    if not media.is_file():
        print(f"ERROR: media not found: {media}", file=sys.stderr)
        return 2
    backend = choose_backend(args.backend)
    model = choose_model(backend, args.model)
    try:
        if backend == "mlx":
            segments, language = transcribe_mlx(media, model, args.language, args.initial_prompt)
        else:
            segments, language = transcribe_faster(
                media, model, args.language, args.initial_prompt, args.device, args.compute_type
            )
        outputs = write_outputs(args.output_dir.expanduser().resolve(), media, backend, model, language, segments)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"backend": backend, "model": model, "segments": len(segments), "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
