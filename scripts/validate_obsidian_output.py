#!/usr/bin/env python3
"""检查暂存 Obsidian 样板的文件、中文命名和双链完整性。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
英文属性 = re.compile(r"(?m)^[A-Za-z][A-Za-z0-9_]*:")
英文看板属性 = re.compile(r"\bnote\.[A-Za-z][A-Za-z0-9_]*\b")
英文看板排序字段 = re.compile(r"(?m)^\s*-\s*property:\s*([A-Za-z][A-Za-z0-9_]*)\s*$")
英文可见表头 = re.compile(r"(?m)^\s*displayName:\s*.*[A-Za-z]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("库目录", type=Path)
    args = parser.parse_args()
    root = args.库目录.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    markdown = sorted(root.rglob("*.md"))
    bases = sorted(root.rglob("*.base"))

    required_folders = ["直播场次", "完整文字稿", "连线案件", "实务知识", "唠嗑价值", "_系统数据"]
    for name in required_folders:
        if not (root / name).is_dir():
            errors.append(f"缺少目录：{name}")
    for name in ["首页.md", "📺 直播场次.base", "📝 完整文字稿.base", "⚖️ 连线案件.base", "💡 实务知识.base", "☕ 唠嗑价值.base", "🔎 待复核.base", "📊 数据总表.base"]:
        if not (root / name).is_file():
            errors.append(f"缺少入口或看板：{name}")

    ids: set[str] = set()
    link_count = 0
    for path in markdown:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"不是 UTF-8：{path.relative_to(root)}")
            continue
        if not text.startswith("---\n"):
            warnings.append(f"缺少 YAML：{path.relative_to(root)}")
        英文字段 = 英文属性.findall(text.split("\n---\n", 1)[0])
        if 英文字段:
            errors.append(f"存在英文属性：{path.relative_to(root)} → {', '.join(x[:-1] for x in 英文字段)}")
        note_type = re.search(r'^类型:\s*["\']?([^"\'\n]+)', text, re.MULTILINE)
        required_relation_fields = {
            "直播场次": ("记录编号", "场次编号", "完整文字稿"),
            "完整文字稿": ("记录编号", "场次编号", "所属直播"),
            "连线案件": ("记录编号", "场次编号", "连线编号", "所属直播", "来源位置"),
            "实务知识": ("记录编号", "场次编号", "关联案件", "所属直播"),
            "唠嗑价值": ("记录编号", "场次编号", "关联案件", "所属直播"),
        }
        if note_type:
            for field in required_relation_fields.get(note_type.group(1), ()):
                if not re.search(rf"^{field}:", text, re.MULTILINE):
                    errors.append(f"缺少关联字段：{path.relative_to(root)} → {field}")
            if note_type.group(1) == "连线案件":
                relative = path.relative_to(root)
                if not re.search(r'^案件文字稿状态:\s*["\']?已附完整文字稿["\']?\s*$', text, re.MULTILINE):
                    errors.append(f"案件未标记完整文字稿：{relative}")
                count_match = re.search(r'^案件文字稿片段数:\s*(\d+)\s*$', text, re.MULTILINE)
                section_count = text.count("\n## 本案完整文字稿\n")
                body_segment_count = len(re.findall(r"(?m)^\*\*整场 \d{2}:\d{2}:\d{2}\.\d{3}–", text))
                if not count_match or int(count_match.group(1)) <= 0:
                    errors.append(f"案件文字稿片段数无效：{relative}")
                elif int(count_match.group(1)) != body_segment_count:
                    errors.append(
                        f"案件文字稿片段数不一致：{relative} → 属性{count_match.group(1)}，正文{body_segment_count}"
                    )
                if section_count != 1:
                    errors.append(f"案件完整文字稿章节数量应为1：{relative} → {section_count}")
                if not re.search(r'^隐私状态:\s*["\']?含敏感原文["\']?\s*$', text, re.MULTILINE):
                    errors.append(f"案件原文未标记敏感：{relative}")
                if "> [!warning] 敏感原文" not in text:
                    errors.append(f"案件完整文字稿缺少敏感提示：{relative}")
        for key in ("记录编号", "案件编号", "知识编号", "唠嗑编号"):
            match = re.search(rf"^{key}:\s*\"([^\"]+)\"", text, re.MULTILINE)
            if match:
                item_id = f"{key}:{match.group(1)}"
                if item_id in ids:
                    errors.append(f"重复编号：{item_id}")
                ids.add(item_id)
        for match in WIKILINK.finditer(text):
            link_count += 1
            target = match.group(1)
            prefix = f"{root.name}/"
            position = target.find(prefix)
            if position >= 0:
                target = target[position + len(prefix):]
            candidate = root / target
            if candidate.suffix:
                exists = candidate.is_file()
            else:
                exists = candidate.with_suffix(".md").is_file() or candidate.with_suffix(".base").is_file()
            if not exists:
                errors.append(f"失效双链：{path.relative_to(root)} → {match.group(1)}")

    for path in bases:
        text = path.read_text(encoding="utf-8")
        fields = sorted(set(英文看板属性.findall(text)))
        if fields:
            errors.append(f"看板仍引用英文属性：{path.relative_to(root)} → {', '.join(fields)}")
        sort_fields = sorted(set(英文看板排序字段.findall(text)))
        if sort_fields:
            errors.append(f"看板仍使用英文排序字段：{path.relative_to(root)} → {', '.join(sort_fields)}")
        if 英文可见表头.search(text):
            errors.append(f"看板存在英文可见表头：{path.relative_to(root)}")
        if path.name == "💡 实务知识.base" and re.search(r"name:\s*全部实务知识\s*\n\s*filters:", text):
            errors.append("全部实务知识视图不应残留临时筛选条件")

    result = {
        "通过": not errors,
        "Markdown文件": len(markdown),
        "Bases看板": len(bases),
        "案件笔记": len(list((root / "连线案件").glob("*.md"))),
        "实务知识": len(list((root / "实务知识").glob("*.md"))),
        "唠嗑价值": len(list((root / "唠嗑价值").glob("*.md"))),
        "完整文字稿": len(list((root / "完整文字稿").rglob("*.md"))),
        "双链数量": link_count,
        "错误": errors,
        "提醒": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
