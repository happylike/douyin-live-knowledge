#!/usr/bin/env python3
"""按录制顺序合并多个分段转写，保存分段内时间与整场累计时间。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def 参数() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("转写文件", nargs="+", type=Path, help="按录制顺序传入 transcript.json")
    parser.add_argument("--场次编号", required=True)
    parser.add_argument("--主播", required=True)
    parser.add_argument("--输出前缀", required=True, type=Path)
    parser.add_argument("--源文件", nargs="*", default=[], help="与转写文件顺序一致的源视频名称")
    return parser.parse_args()


def 时间戳(seconds: float, srt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{',' if srt else '.'}{millis:03d}"


def main() -> int:
    args = 参数()
    if args.源文件 and len(args.源文件) != len(args.转写文件):
        raise SystemExit("错误：--源文件数量必须与转写文件数量一致")
    merged: list[dict] = []
    parts: list[dict] = []
    offset = 0.0
    backends: list[str] = []
    models: list[str] = []
    for index, path in enumerate(args.转写文件):
        raw = json.loads(path.read_text(encoding="utf-8"))
        part = f"{index:03d}"
        source = args.源文件[index] if args.源文件 else Path(str(raw.get("sourcePath", path))).name
        duration = float(raw.get("durationSeconds") or 0)
        if not duration and raw.get("segments"):
            duration = float(raw["segments"][-1].get("end", 0))
        count = 0
        for item in raw.get("segments", []):
            text = " ".join(str(item.get("text", "")).split())
            if not text:
                continue
            local_start = float(item.get("start", 0))
            local_end = float(item.get("end", 0))
            merged.append({
                "index": len(merged) + 1, "sourcePart": part, "sourceFile": source,
                "localStart": round(local_start, 3), "localEnd": round(local_end, 3),
                "wholeStart": round(offset + local_start, 3), "wholeEnd": round(offset + local_end, 3), "text": text,
            })
            count += 1
        parts.append({"sourcePart": part, "sourceFile": source, "durationSeconds": round(duration, 3),
                      "wholeStart": round(offset, 3), "wholeEnd": round(offset + duration, 3), "segmentCount": count})
        offset += duration
        backends.append(str(raw.get("backend", "")))
        models.append(str(raw.get("model", "")))
    counts = Counter(item["text"] for item in merged)
    repeat_ratio = max(counts.values(), default=0) / max(len(merged), 1)
    payload = {
        "schemaVersion": 1, "sessionId": args.场次编号, "host": args.主播,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "backend": next((x for x in backends if x), ""), "model": next((x for x in models if x), ""),
        "language": "Chinese", "durationSeconds": round(offset, 3), "segmentCount": len(merged),
        "sourcePartCount": len(parts), "parts": parts, "segments": merged,
        "quality": {"status": "review", "highestExactRepeatRatio": round(repeat_ratio, 6), "warnings": [
            "机器识别原始稿必须人工复核关键事实。", "跨分段案件应按整场累计时间连接。", "原始稿含敏感内容，不应公开发布。"
        ]},
    }
    stem = args.输出前缀
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".txt").write_text("\n".join(x["text"] for x in merged) + "\n", encoding="utf-8")
    stem.with_suffix(".srt").write_text("".join(
        f"{x['index']}\n{时间戳(x['wholeStart'], True)} --> {时间戳(x['wholeEnd'], True)}\n{x['text']}\n\n" for x in merged
    ), encoding="utf-8")
    lines = [f"# {args.主播}整场直播完整文字稿", "", f"> 场次编号：`{args.场次编号}`  ",
             f"> 来源分段：{len(parts)}段  ", f"> 整场时长：`{时间戳(offset)}`  ",
             "> 状态：机器识别原始稿，关键事实必须复核", ""]
    current = None
    for item in merged:
        if item["sourcePart"] != current:
            current = item["sourcePart"]
            lines.extend([f"## 来源分段 {current}", ""])
        lines.extend([f"### 整场 {时间戳(item['wholeStart'])}–{时间戳(item['wholeEnd'])}（{current} {时间戳(item['localStart'])}–{时间戳(item['localEnd'])}）", "", item["text"], ""])
    stem.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"整场时长": 时间戳(offset), "分段数": len(parts), "识别块数": len(merged), "最高重复比例": round(repeat_ratio, 6)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
