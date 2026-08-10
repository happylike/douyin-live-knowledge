# Analysis schema

## Contents

1. Output contract
2. Item rules
3. Importance rubric
4. Analysis procedure

## Output contract

Write UTF-8 JSON with this shape. Use empty lists or empty strings instead of omitting required keys.

```json
{
  "schemaVersion": 1,
  "session": {
    "sessionId": "host-YYYYMMDD-HHMMSS",
    "host": "主播名",
    "platform": "douyin",
    "startedAt": "2026-08-05T20:52:55+08:00",
    "endedAt": "2026-08-05T21:22:55+08:00",
    "title": "本场直播概括",
    "overview": "整场概况",
    "importance": 4,
    "sourceFiles": ["absolute-or-original-file-name.mp4"],
    "topics": ["交通事故"],
    "warnings": ["自动转写可能混淆专有名词"]
  },
  "cases": [
    {
      "caseId": "host-YYYYMMDD-01",
      "title": "匿名且可检索的案件标题",
      "importance": 5,
      "importanceReason": "为什么属于这一重要度",
      "confidence": 0.86,
      "category": ["交通事故"],
      "callerRole": "咨询人在事件中的角色",
      "answerStatus": "partial",
      "hasDeadlineRisk": false,
      "facts": ["仅写咨询人明确陈述的事实"],
      "questions": ["咨询人具体询问的问题"],
      "hostReasoning": ["主播的分析过程"],
      "hostAnswer": ["主播明确给出的回答"],
      "actionPlan": ["按先后顺序排列的处理步骤"],
      "evidenceAdvice": ["建议保存或取得的证据"],
      "deadlines": ["提到的期限；未提及则为空"],
      "risks": ["程序、证据、实体或沟通风险"],
      "reusableLessons": ["能用于其他事务的经验"],
      "needsLegalVerification": true,
      "verificationNotes": ["应核验的法条、地域规则或事实"],
      "sourceStart": "00:03:12",
      "sourceEnd": "00:18:46",
      "sourceRanges": [
        {"start": "00:03:12", "end": "00:10:00", "sourceFile": "recording_000.mp4"},
        {"start": "00:45:00", "end": "00:52:00", "sourceFile": "recording_001.mp4"}
      ],
      "sourceFiles": ["recording_000.mp4"],
      "keyQuotes": [{"timestamp": "00:12:10", "text": "不超过必要长度的关键原话"}]
    }
  ],
  "knowledge": [
    {
      "knowledgeId": "host-YYYYMMDD-k01",
      "title": "可复用知识标题",
      "importance": 4,
      "category": ["证据", "沟通"],
      "summary": "知识点本身",
      "application": ["适用场景与使用方法"],
      "limits": ["例外、边界和待核实内容"],
      "relatedCaseIds": ["host-YYYYMMDD-01"],
      "sourceStart": "00:10:00",
      "sourceEnd": "00:14:00"
    }
  ],
  "valuableChat": [
    {
      "chatId": "host-YYYYMMDD-c01",
      "title": "闲聊中的价值标题",
      "importance": 2,
      "valueType": ["情绪疏导", "人情世故"],
      "relatedCaseIds": ["host-YYYYMMDD-01"],
      "summary": "保留语境的内容概括",
      "practicalValue": ["为什么值得保留、可以怎么用"],
      "sourceStart": "00:20:00",
      "sourceEnd": "00:24:00"
    }
  ],
  "timeline": [
    {
      "start": "00:00:00",
      "end": "00:03:11",
      "type": "普通互动",
      "importance": 1,
      "summary": "该时间段发生了什么",
      "linkedIds": []
    }
  ]
}
```

## Item rules

- A case may span source files. Keep one case ID and list all contributing files.
- Use `sourceRanges` when a case is interrupted, reconnects, or crosses files. Never imply that unrelated material between two appearances belongs to the case.
- `sourceRanges` is also the rendering contract for the complete transcript appended to the case note. Include every case appearance precisely; do not replace multiple ranges with one broad `sourceStart`–`sourceEnd` span.
- Set `answerStatus` to `none`, `partial`, or `substantive`. A list containing only requests for more facts is `partial`, not `substantive`.
- Set `hasDeadlineRisk` explicitly. Do not infer it merely because a note mentions elapsed time.
- Do not infer missing facts. Put ambiguity in `verificationNotes`.
- `confidence` measures confidence in the extraction, not the legal correctness of the answer.
- A knowledge item must be reusable beyond its source case. Otherwise keep it under `reusableLessons` only.
- Valuable chat must state its practical value. Pure greetings, gifts, advertisements, and repeated audience interaction remain only in the timeline and transcript.
- Cover the entire transcript with non-overlapping timeline entries where practical. Gaps are allowed only for silence or corrupt media.

## Importance rubric

- `5`: Complete, directly reusable case strategy, decisive evidence/deadline/risk guidance, or unusually important professional insight.
- `4`: Clear question and substantive answer with strong reusable value.
- `3`: Useful but incomplete facts, answer, or knowledge.
- `2`: Weak or contextual value, including useful communication, emotional, relationship, or professional chat.
- `1`: Routine interaction, repetition, greetings, entertainment, or advertising. Preserve it in the transcript/timeline.

## Analysis procedure

1. Read timestamped segments, not only the concatenated text.
2. Mark speaker or role changes when reasonably inferable; label uncertainty instead of inventing identities.
3. Locate consultation boundaries using entry/exit phrases, topic changes, and question-answer structure.
4. Draft the full timeline.
5. Build cases from timeline spans.
6. Extract reusable knowledge and valuable chat.
7. Check that every ID is unique and every extracted item has timestamps.
8. Check that derived notes contain no unnecessary personal identifiers.
