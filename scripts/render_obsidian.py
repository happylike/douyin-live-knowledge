#!/usr/bin/env python3
"""把审核过的整场直播分析渲染为全中文 Obsidian 知识库与 Bases。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def 参数() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True, help="符合分析结构的 JSON")
    parser.add_argument("--transcript", type=Path, required=True, help="单段或整场合并文字稿 JSON")
    parser.add_argument("--output-root", type=Path, required=True, help="抖音直播知识库根目录；程序会自动建立主播一级目录")
    parser.add_argument("--vault-folder", default="抖音直播知识库", help="知识库根目录相对 Vault 的路径")
    return parser.parse_args()


def 安全文件名(value: str, limit: int = 100) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#^[\]]+", "-", value).strip(" .-")
    return (cleaned or "未命名")[:limit]


def yaml值(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def 属性区(properties: dict[str, Any]) -> str:
    return "---\n" + "\n".join(f"{key}: {yaml值(value)}" for key, value in properties.items()) + "\n---\n"


def 列表章节(title: str, values: list[str]) -> str:
    body = "\n".join(f"- {value}" for value in values) if values else "- 未明确提及"
    return f"## {title}\n\n{body}\n"


def 一句话(values: list[str], default: str = "待补充") -> str:
    return values[0].strip() if values and values[0].strip() else default


def 写笔记(path: Path, properties: dict[str, Any], title: str, sections: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = 属性区(properties) + f"# {title}\n\n" + "\n".join(sections).rstrip() + "\n"
    path.write_text(body, encoding="utf-8")


def 双链(vault_folder: str, relative: Path) -> str:
    return f"[[{vault_folder}/{relative.with_suffix('').as_posix()}]]"


def 时间戳(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def 解析时间(value: str) -> float:
    """把 HH:MM:SS(.mmm) 转为秒。"""
    hours, minutes, seconds = str(value).split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def 中文时长(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分{secs}秒"
    return f"{minutes}分{secs}秒"


def 重要程度(value: int) -> str:
    return {5: "5-最高", 4: "4-核心", 3: "3-重要", 2: "2-参考", 1: "1-一般"}.get(value, f"{value}-待定")


def 回答状态(value: str) -> str:
    return {"substantive": "实质回答", "partial": "部分回答", "none": "未回答"}.get(value, "待判断")


def 来源概括(item: dict[str, Any]) -> str:
    ranges = item.get("sourceRanges", [])
    if ranges:
        return "；".join(
            f"{Path(str(value.get('sourceFile', ''))).stem.rsplit('_', 1)[-1]} {value.get('start', '')}–{value.get('end', '')}"
            for value in ranges
        )
    return f"整场 {item.get('sourceStart', '')}–{item.get('sourceEnd', '')}"


def 案件完整文字稿(item: dict[str, Any], transcript: dict[str, Any]) -> tuple[str, int]:
    """按案件的每个来源时间段完整摘录 ASR 分段，断线续接不夹入无关内容。"""
    ranges = item.get("sourceRanges") or []
    if not ranges:
        raise ValueError(f"{item.get('caseId', '未知案件')} 缺少 sourceRanges，无法附加案件完整文字稿")

    parts = transcript.get("parts") or []
    exact_parts = {str(part.get("sourceFile", "")): part for part in parts}
    basename_parts: dict[str, dict[str, Any] | None] = {}
    for part in parts:
        name = Path(str(part.get("sourceFile", ""))).name
        basename_parts[name] = None if name in basename_parts else part

    sections = [
        "## 本案完整文字稿",
        "",
        "> [!warning] 敏感原文",
        "> 本节按案件来源时间段从整场机器识别稿完整摘录，可能包含未经脱敏的咨询原话。仅限私密归档；对外引用数字、姓名、机构名或关键原话前，应回到原音视频确认。",
        "> 案件边界以语音识别分段为最小单位，边界片段可能与相邻案件有少量重叠。",
        "",
    ]
    segment_count = 0
    transcript_segments = transcript.get("segments") or []
    for range_index, source_range in enumerate(ranges, 1):
        source_file = str(source_range.get("sourceFile", ""))
        part = exact_parts.get(source_file)
        if part is None:
            part = basename_parts.get(Path(source_file).name)
        if part is None:
            raise ValueError(f"{item['caseId']} 找不到来源分段：{source_file}")

        local_left = 解析时间(str(source_range.get("start", "")))
        local_right = 解析时间(str(source_range.get("end", "")))
        if local_right <= local_left:
            raise ValueError(f"{item['caseId']} 的来源时间段无效：{source_range}")
        whole_left = float(part.get("wholeStart", 0)) + local_left
        whole_right = float(part.get("wholeStart", 0)) + local_right
        part_source_file = str(part.get("sourceFile", ""))
        selected = [
            segment for segment in transcript_segments
            if str(segment.get("sourceFile", "")) == part_source_file
            and float(segment.get("wholeEnd", segment.get("end", 0))) > whole_left
            and float(segment.get("wholeStart", segment.get("start", 0))) < whole_right
        ]
        selected.sort(key=lambda segment: (
            float(segment.get("wholeStart", segment.get("start", 0))),
            int(segment.get("index", 0)),
        ))
        if not selected:
            raise ValueError(f"{item['caseId']} 的来源时间段没有匹配文字稿：{source_range}")

        source_part = str(part.get("sourcePart", selected[0].get("sourcePart", "000")))
        sections.extend([
            f"### 来源时间段 {range_index} · 整场 {时间戳(whole_left)}–{时间戳(whole_right)}",
            "",
            f"- 来源文件：`{source_file}`",
            f"- 分段位置：`{source_part} {时间戳(local_left)}–{时间戳(local_right)}`",
            "",
        ])
        for segment in selected:
            whole_start = float(segment.get("wholeStart", segment.get("start", 0)))
            whole_end = float(segment.get("wholeEnd", segment.get("end", 0)))
            local_start = float(segment.get("localStart", segment.get("start", 0)))
            local_end = float(segment.get("localEnd", segment.get("end", 0)))
            text = str(segment.get("text", "")).strip() or "[无可识别语音]"
            sections.extend([
                f"**整场 {时间戳(whole_start)}–{时间戳(whole_end)}**（{segment.get('sourcePart', source_part)} {时间戳(local_start)}–{时间戳(local_end)}）  ",
                text,
                "",
            ])
            segment_count += 1
    return "\n".join(sections).rstrip() + "\n", segment_count


def 安装看板(root: Path) -> None:
    assets = Path(__file__).resolve().parents[1] / "assets" / "obsidian-bases"
    for source in assets.glob("*.base"):
        (root / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def 写完整文字稿(root: Path, vault_folder: str, session: dict[str, Any], session_link: str, transcript: dict[str, Any]) -> tuple[Path, str]:
    session_id = session["sessionId"]
    relative = Path("完整文字稿") / f"{安全文件名(session_id)} 整场完整文字稿.md"
    segments = transcript.get("segments", [])
    duration = float(transcript.get("durationSeconds") or 0)
    if not duration and segments:
        duration = float(segments[-1].get("wholeEnd", segments[-1].get("end", 0)))
    parts = transcript.get("parts", [])
    part_count = int(transcript.get("sourcePartCount") or len(parts) or len(session.get("sourceFiles", [])) or 1)
    model = Path(str(transcript.get("model", "未知模型"))).name
    lines = [
        f"# {session.get('host', '未知主播')}整场直播完整文字稿",
        "",
        f"> 场次编号：`{session_id}`  ",
        f"> 整场时长：`{时间戳(duration)}`  ",
        f"> 识别模型：`{model}`  ",
        "> 状态：机器识别原始稿，关键事实与法律表述必须复核  ",
        "> 说明：保留整场累计时间；原文含敏感咨询内容，不应公开发布",
        "",
    ]
    current_part: str | None = None
    for item in segments:
        part = str(item.get("sourcePart", "000"))
        if part != current_part:
            current_part = part
            lines.extend([f"## 来源分段 {part}", ""])
        start = float(item.get("wholeStart", item.get("start", 0)))
        end = float(item.get("wholeEnd", item.get("end", 0)))
        local_start = float(item.get("localStart", item.get("start", 0)))
        local_end = float(item.get("localEnd", item.get("end", 0)))
        lines.extend([
            f"### 整场 {时间戳(start)}–{时间戳(end)}（{part} {时间戳(local_start)}–{时间戳(local_end)}）",
            "",
            str(item.get("text", "")).strip(),
            "",
        ])
    properties = {
        "类型": "完整文字稿",
        "平台": "抖音",
        "记录编号": f"{session_id}-完整文字稿",
        "场次编号": session_id,
        "主播": session.get("host", "未知主播"),
        "用途": "整场完整文字稿",
        "源文件": session.get("sourceFiles", []),
        "覆盖分段概况": f"共{part_count}段",
        "分段总数": part_count,
        "整场秒数": round(duration, 3),
        "整场时长": 中文时长(duration),
        "转写后端": transcript.get("backend", ""),
        "识别模型": model,
        "处理状态": "整场转写完成",
        "复核状态": "待逐句复核",
        "复核原因": "罪名、金额、人数、期限、专有名词和机构名需复核",
        "需要重听": True,
        "隐私状态": "含敏感原文",
        "所属直播": session_link,
        "来源位置": f"整场 00:00:00–{时间戳(duration).split('.')[0]}",
        "标签": ["抖音直播", "完整文字稿", "敏感内容"],
    }
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(属性区(properties) + "\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return relative, 双链(vault_folder, relative)


def main() -> int:
    args = 参数()
    try:
        analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
        transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    if analysis.get("schemaVersion") != 1 or not isinstance(analysis.get("session"), dict):
        print("错误：分析文件必须符合第一版分析结构", file=sys.stderr)
        return 2

    library_root = args.output_root.expanduser().resolve()
    session = analysis["session"]
    host = session.get("host", "未知主播")
    host_folder = 安全文件名(host)
    root = library_root / host_folder
    host_vault_folder = f"{args.vault_folder.rstrip('/')}/{host_folder}"
    for folder in ("直播场次", "完整文字稿", "连线案件", "实务知识", "唠嗑价值", "_系统数据"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    session_id = session["sessionId"]
    session_relative = Path("直播场次") / f"{安全文件名(session_id)} {安全文件名(session['title'])}.md"
    session_link = 双链(host_vault_folder, session_relative)

    case_links: list[str] = []
    case_link_map: dict[str, str] = {}
    for index, item in enumerate(analysis.get("cases", []), 1):
        relative = Path("连线案件") / f"{安全文件名(item['caseId'])} {安全文件名(item['title'])}.md"
        link = 双链(host_vault_folder, relative)
        case_links.append(link)
        case_link_map[item["caseId"]] = link
        ranges = item.get("sourceRanges") or [{"start": item.get("sourceStart", ""), "end": item.get("sourceEnd", ""), "sourceFile": ""}]
        range_lines = "\n".join(f"- `{x.get('start', '')}`–`{x.get('end', '')}` · {x.get('sourceFile', '')}" for x in ranges)
        quotes = "\n".join(f"- `{x.get('timestamp', '')}` {x.get('text', '')}" for x in item.get("keyQuotes", [])) or "- 无"
        verification = bool(item.get("needsLegalVerification", True))
        importance = int(item.get("importance", 1))
        status = 回答状态(str(item.get("answerStatus", "partial")))
        case_transcript, case_transcript_segments = 案件完整文字稿(item, transcript)
        写笔记(root / relative, {
            "类型": "连线案件", "平台": "抖音", "记录编号": item["caseId"], "场次编号": session_id,
            "案件编号": item["caseId"], "连线编号": f"连线{index:02d}", "连线人代称": f"连线人{index:02d}",
            "主播": host, "重要度": importance, "重要程度": 重要程度(importance), "识别置信度": item.get("confidence", 0),
            "案件领域": item.get("category", []), "咨询人角色": item.get("callerRole", "未知"), "回答状态": status,
            "复核状态": "待人工复核", "复核原因": "关键事实、转写和法律结论待确认",
            "法律核验状态": "待核验" if verification else "无需专项核验", "有明确回答": status == "实质回答",
            "有处理步骤": bool(item.get("actionPlan")), "有证据建议": bool(item.get("evidenceAdvice")),
            "有期限风险": bool(item.get("hasDeadlineRisk", False)), "需要法律核验": verification,
            "需要重听": bool(item.get("needsRelisten", False)), "隐私状态": "含敏感原文",
            "案件文字稿状态": "已附完整文字稿", "案件文字稿片段数": case_transcript_segments, "所属直播": session_link,
            "源文件": item.get("sourceFiles", []), "来源开始": item.get("sourceStart", ""), "来源结束": item.get("sourceEnd", ""),
            "来源时间段": [f"{x.get('start', '')}–{x.get('end', '')}" for x in ranges], "来源位置": 来源概括(item),
            "咨询问题摘要": 一句话(item.get("questions", [])), "回答要点摘要": 一句话(item.get("hostAnswer", []), "本场未形成完整回答"),
            "处理方向摘要": 一句话(item.get("actionPlan", []), "待补充处理方向"),
            "标签": ["抖音直播", "连线案件", *item.get("category", [])],
        }, item["title"], [
            列表章节("当事人陈述的案件情况", item.get("facts", [])), 列表章节("咨询人具体问了什么", item.get("questions", [])),
            列表章节("主播如何分析", item.get("hostReasoning", [])), 列表章节("主播给出的回答", item.get("hostAnswer", [])),
            列表章节("建议的处理步骤", item.get("actionPlan", [])), 列表章节("证据建议", item.get("evidenceAdvice", [])),
            列表章节("期限", item.get("deadlines", [])), 列表章节("风险", item.get("risks", [])),
            列表章节("可复用于其他事务的经验", item.get("reusableLessons", [])), 列表章节("需要核验", item.get("verificationNotes", [])),
            f"## 关键原话\n\n{quotes}\n", f"## 来源\n\n- 所属直播：{session_link}\n{range_lines}\n", case_transcript,
        ])

    knowledge_links: list[str] = []
    for item in analysis.get("knowledge", []):
        relative = Path("实务知识") / f"{安全文件名(item['knowledgeId'])} {安全文件名(item['title'])}.md"
        link = 双链(host_vault_folder, relative)
        knowledge_links.append(link)
        related = [case_link_map[x] for x in item.get("relatedCaseIds", []) if x in case_link_map]
        importance = int(item.get("importance", 1))
        写笔记(root / relative, {
            "类型": "实务知识", "平台": "抖音", "记录编号": item["knowledgeId"], "知识编号": item["knowledgeId"],
            "场次编号": session_id, "主播": host, "重要度": importance, "重要程度": 重要程度(importance),
            "知识分类": item.get("category", []), "知识摘要": item.get("summary", ""),
            "实务用途摘要": 一句话(item.get("application", [])), "关联案件": related,
            "复核状态": "待人工复核", "复核原因": "知识结论、适用边界与法律依据待核验",
            "法律核验状态": "待核验", "所属直播": session_link, "来源开始": item.get("sourceStart", ""),
            "来源结束": item.get("sourceEnd", ""), "来源位置": 来源概括(item),
            "标签": ["抖音直播", "实务知识", *item.get("category", [])],
        }, item["title"], [f"## 知识点\n\n{item.get('summary', '')}\n", 列表章节("适用方法", item.get("application", [])),
            列表章节("边界与限制", item.get("limits", [])), f"## 来源\n\n- 所属直播：{session_link}\n- 时间：`{item.get('sourceStart', '')}`–`{item.get('sourceEnd', '')}`\n"])

    chat_case_map: dict[str, list[str]] = {}
    for row in analysis.get("timeline", []):
        cases = [x for x in row.get("linkedIds", []) if x in case_link_map]
        for linked_id in row.get("linkedIds", []):
            if linked_id in {x.get("chatId") for x in analysis.get("valuableChat", [])}:
                chat_case_map.setdefault(linked_id, []).extend(cases)
    chat_links: list[str] = []
    for item in analysis.get("valuableChat", []):
        relative = Path("唠嗑价值") / f"{安全文件名(item['chatId'])} {安全文件名(item['title'])}.md"
        link = 双链(host_vault_folder, relative)
        chat_links.append(link)
        ids = list(dict.fromkeys([*item.get("relatedCaseIds", []), *chat_case_map.get(item["chatId"], [])]))
        related = [case_link_map[x] for x in ids if x in case_link_map]
        importance = int(item.get("importance", 1))
        写笔记(root / relative, {
            "类型": "唠嗑价值", "平台": "抖音", "记录编号": item["chatId"], "唠嗑编号": item["chatId"],
            "场次编号": session_id, "主播": host, "重要度": importance, "重要程度": 重要程度(importance),
            "价值类型": item.get("valueType", []), "内容摘要": item.get("summary", ""),
            "可复用价值摘要": 一句话(item.get("practicalValue", [])), "关联案件": related,
            "复核状态": "待人工复核", "复核原因": "需确认长期保留价值和适用场景",
            "所属直播": session_link, "来源开始": item.get("sourceStart", ""), "来源结束": item.get("sourceEnd", ""),
            "来源位置": 来源概括(item), "标签": ["抖音直播", "唠嗑价值", *item.get("valueType", [])],
        }, item["title"], [f"## 内容概括\n\n{item.get('summary', '')}\n", 列表章节("实际价值", item.get("practicalValue", [])),
            f"## 来源\n\n- 所属直播：{session_link}\n- 时间：`{item.get('sourceStart', '')}`–`{item.get('sourceEnd', '')}`\n"])

    transcript_relative, transcript_link = 写完整文字稿(root, host_vault_folder, session, session_link, transcript)
    duration = float(transcript.get("durationSeconds") or 0)
    part_count = int(transcript.get("sourcePartCount") or len(transcript.get("parts", [])) or len(session.get("sourceFiles", [])) or 1)
    timeline = "\n".join(f"- `{x.get('start', '')}`–`{x.get('end', '')}` · **{x.get('type', '')}** · 重要度{x.get('importance', 1)}：{x.get('summary', '')}" for x in analysis.get("timeline", [])) or "- 无"
    importance = int(session.get("importance", 1))
    写笔记(root / session_relative, {
        "类型": "直播场次", "平台": "抖音", "记录编号": session_id, "场次编号": session_id, "主播": host,
        "开播时间": session.get("startedAt", ""), "整场结束时间": session.get("endedAt", ""), "整场秒数": round(duration, 3),
        "整场时长": 中文时长(duration), "重要度": importance, "重要程度": 重要程度(importance), "主题": session.get("topics", []),
        "案件数量": len(case_links), "核心案件数量": sum(int(x.get("importance", 1)) >= 4 for x in analysis.get("cases", [])),
        "知识点数量": len(knowledge_links), "唠嗑价值数量": len(chat_links), "源文件": session.get("sourceFiles", []),
        "分段总数": part_count, "已处理分段数": part_count, "分段进度": f"{part_count}/{part_count}", "处理状态": "整场处理完成",
        "复核状态": "待人工复核", "复核原因": "整场摘要、案件切分和法律结论均需人工确认",
        "隐私状态": "派生笔记已脱敏", "完整文字稿": transcript_link, "标签": ["抖音直播", "直播场次"],
    }, session["title"], [f"## 整场概况\n\n{session.get('overview', '')}\n",
        "## 连线案件\n\n" + ("\n".join(f"- {x}" for x in case_links) if case_links else "- 本场未识别到完整案件") + "\n",
        "## 实务知识\n\n" + ("\n".join(f"- {x}" for x in knowledge_links) if knowledge_links else "- 无单独知识卡片") + "\n",
        "## 唠嗑价值\n\n" + ("\n".join(f"- {x}" for x in chat_links) if chat_links else "- 无单独价值卡片") + "\n",
        f"## 内容时间轴\n\n{timeline}\n", f"## 完整文字稿\n\n- {transcript_link}\n", 列表章节("注意事项", session.get("warnings", []))])

    (root / "首页.md").write_text(属性区({"标题": "抖音直播知识库"}) + "# 抖音直播知识库\n\n## 数据看板\n\n" + "\n".join([
        f"- [[{host_vault_folder}/📺 直播场次.base|直播场次看板]]", f"- [[{host_vault_folder}/📝 完整文字稿.base|完整文字稿看板]]",
        f"- [[{host_vault_folder}/⚖️ 连线案件.base|连线案件看板]]", f"- [[{host_vault_folder}/💡 实务知识.base|实务知识看板]]",
        f"- [[{host_vault_folder}/☕ 唠嗑价值.base|唠嗑价值看板]]", f"- [[{host_vault_folder}/🔎 待复核.base|待复核看板]]",
        f"- [[{host_vault_folder}/📊 数据总表.base|数据总表]]", "", "## 本场入口", "", f"- {session_link}", f"- {transcript_link}", "",
    ]), encoding="utf-8")
    relation_source = Path(__file__).resolve().parents[1] / "references" / "obsidian-data-model.md"
    if relation_source.is_file():
        (root / "数据关系说明.md").write_text(属性区({"标题": "直播知识库数据关系说明"}) + relation_source.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "_系统数据" / f"{安全文件名(session_id)}.分析.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "_系统数据" / f"{安全文件名(session_id)}.文字稿.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    安装看板(root)
    library_root.mkdir(parents=True, exist_ok=True)
    global_home = library_root / "首页.md"
    host_home_link = f"[[{host_vault_folder}/首页|{host}知识库]]"
    if global_home.is_file():
        global_text = global_home.read_text(encoding="utf-8")
        if host_home_link not in global_text:
            global_home.write_text(global_text.rstrip() + f"\n- {host_home_link}\n", encoding="utf-8")
    else:
        global_home.write_text(属性区({"标题": "抖音直播知识库主播总入口"}) + f"# 抖音直播知识库\n\n## 主播目录\n\n- {host_home_link}\n", encoding="utf-8")
    print(json.dumps({"知识库根目录": str(library_root), "主播目录": str(root), "直播场次": 1, "完整文字稿": 1, "连线案件": len(case_links), "实务知识": len(knowledge_links), "唠嗑价值": len(chat_links), "看板": 7}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
