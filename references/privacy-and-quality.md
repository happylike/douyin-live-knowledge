# Privacy and quality

## Sensitive information

Redact from case summaries and metadata, knowledge notes, and chat notes:

- full names of callers and unrelated individuals;
- telephone, account, ID, licence plate, and case numbers;
- detailed home or work addresses;
- employer names when they identify a private person and are not analytically necessary;
- health, family, financial, or criminal details not needed to understand the issue.

Use neutral roles such as `咨询人`、`对方`、`某公司`、`家属`. Keep the original media untouched. Every case note must retain a complete timestamped archival transcript for that case after the redacted summary. Mark the note `隐私状态: 含敏感原文`, add a visible sensitive-content warning before the transcript, and do not expose transcript text through broad dashboard properties.

For interrupted or reconnected calls, extract each `sourceRanges` interval separately. Do not include unrelated speech between appearances merely because it falls between the case's earliest and latest whole-session timestamps. The ASR segment is the smallest archival unit, so boundary segments may overlap adjacent cases slightly; disclose that limitation in the note.

## Legal-quality boundaries

- Attribute advice to the host: write `主播认为` or `主播建议`.
- Do not state that an outcome is guaranteed.
- Mark law, limitation periods, jurisdiction, local policy, and procedural claims for verification when not independently checked.
- Distinguish transcription correction from substantive correction. Fix obvious homophones only when context makes the correction highly likely.
- Preserve disputed or unclear phrases as `[识别存疑：…]`.
- Keep short key quotes for traceability; prefer paraphrase elsewhere.

## Review triggers

Set `needsLegalVerification: true` when the answer includes a deadline, criminal characterization, definitive liability ratio, jurisdiction rule, guaranteed result, or statutory citation. Flag a segment for transcript review when speech is overlapped, music is loud, a proper noun is central, or confidence is materially lower than surrounding segments.
