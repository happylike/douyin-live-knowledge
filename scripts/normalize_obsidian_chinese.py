#!/usr/bin/env python3
"""把暂存知识库的用户属性统一为中文，并同步修正 Bases 字段引用。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


属性映射 = {
    "type": "类型",
    "typeZh": "类型",
    "platform": "平台",
    "host": "主播",
    "session": "所属直播",
    "parentSession": "所属直播",
    "sessionId": "场次编号",
    "sessionKey": "场次编号",
    "recordId": "记录编号",
    "caseId": "案件编号",
    "knowledgeId": "知识编号",
    "chatId": "唠嗑编号",
    "connectionNo": "连线编号",
    "callerAlias": "连线人代称",
    "callerRole": "咨询人角色",
    "importance": "重要度",
    "importanceLevelZh": "重要程度",
    "confidence": "识别置信度",
    "caseCategory": "案件领域",
    "knowledgeCategory": "知识分类",
    "valueType": "价值类型",
    "answerStatus": "回答状态",
    "answerStatusZh": "回答状态",
    "hasClearAnswer": "有明确回答",
    "hasActionPlan": "有处理步骤",
    "hasEvidenceAdvice": "有证据建议",
    "hasDeadlineRisk": "有期限风险",
    "needsLegalVerification": "需要法律核验",
    "needsRelisten": "需要重听",
    "privacyRedacted": "隐私已脱敏",
    "containsSensitiveContent": "包含敏感内容",
    "reviewStatusZh": "复核状态",
    "legalStatusZh": "法律核验状态",
    "reviewReasonZh": "复核原因",
    "questionSummary": "咨询问题摘要",
    "answerSummary": "回答要点摘要",
    "actionSummary": "处理方向摘要",
    "knowledgeSummary": "知识摘要",
    "applicationSummary": "实务用途摘要",
    "chatSummary": "内容摘要",
    "practicalValueSummary": "可复用价值摘要",
    "relatedCaseIds": "关联案件编号",
    "relatedCases": "关联案件",
    "sourceStart": "来源开始",
    "sourceEnd": "来源结束",
    "sourceFiles": "源文件",
    "sourcePartIds": "来源分段",
    "sourceRanges": "来源时间段",
    "sourceRangeSummary": "来源位置",
    "startedAt": "开播时间",
    "endedAt": "整场结束时间",
    "durationSeconds": "整场秒数",
    "durationZh": "整场时长",
    "partCount": "分段总数",
    "processedPartCount": "已处理分段数",
    "partProgressZh": "分段进度",
    "processingStatusZh": "处理状态",
    "caseCount": "案件数量",
    "coreCaseCount": "核心案件数量",
    "knowledgeCount": "知识点数量",
    "valuableChatCount": "唠嗑价值数量",
    "topics": "主题",
    "transcript": "完整文字稿",
    "transcriptLink": "完整文字稿",
    "transcriptionBackend": "转写后端",
    "transcriptionModel": "转写模型路径",
    "transcriptionModelZh": "识别模型",
    "coveredPartsZh": "覆盖分段概况",
    "purposeZh": "用途",
    "timePrecisionZh": "时间精度",
    "title": "标题",
    "tags": "标签",
}


类型值映射 = {
    "douyin-live-session": "直播场次",
    "douyin-live-transcript": "完整文字稿",
    "douyin-live-case": "连线案件",
    "douyin-live-knowledge": "实务知识",
    "douyin-live-chat-value": "唠嗑价值",
    "douyin": "抖音",
    "substantive": "实质回答",
}


def 中文化笔记(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        return False
    yaml_text, body = text.split("\n---\n", 1)
    lines = yaml_text.splitlines()
    已有属性 = {
        match.group(1)
        for line in lines
        if (match := re.match(r"^([^\s:#][^:]*):", line))
    }
    输出: list[str] = []
    已输出: set[str] = set()
    for line in lines:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_]*):(.*)$", line)
        if not match:
            输出.append(line)
            key_match = re.match(r"^([^\s:#][^:]*):", line)
            if key_match:
                已输出.add(key_match.group(1))
            continue
        旧属性, value = match.groups()
        新属性 = 属性映射.get(旧属性)
        if not 新属性:
            输出.append(line)
            continue
        if 新属性 in 已有属性 or 新属性 in 已输出:
            continue
        新行 = f"{新属性}:{value}"
        if 新属性 == "平台":
            新行 = 新行.replace('"douyin"', '"抖音"')
        输出.append(新行)
        已输出.add(新属性)
    new_text = "\n".join(输出) + "\n---\n" + body
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def 中文化看板(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new = text
    for 旧属性, 新属性 in sorted(属性映射.items(), key=lambda item: -len(item[0])):
        new = new.replace(f"note.{旧属性}", f"note.{新属性}")
        new = re.sub(rf"(?m)^(\s*-\s+){re.escape(旧属性)}(?=\s|$)", rf"\1{新属性}", new)
        new = re.sub(
            rf"(?m)^(\s*(?:-\s*)?property:\s*){re.escape(旧属性)}\s*$",
            rf"\1{新属性}",
            new,
        )
    for 旧值, 新值 in 类型值映射.items():
        new = new.replace(f'"{旧值}"', f'"{新值}"')
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("库目录", type=Path)
    args = parser.parse_args()
    root = args.库目录.resolve()
    笔记数 = sum(中文化笔记(path) for path in root.rglob("*.md"))
    看板数 = sum(中文化看板(path) for path in root.rglob("*.base"))
    print(f"已中文化笔记：{笔记数}")
    print(f"已中文化看板：{看板数}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
