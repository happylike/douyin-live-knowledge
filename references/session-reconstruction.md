# Session reconstruction

## Filename pattern

Expect recorder names such as:

```text
主播_2026-08-05_20-52-55_000.mp4
主播_2026-08-05_20-52-55_001.mp4
```

The timestamp identifies a recording run; the numeric suffix identifies a split within that run. A network reconnect may create a new timestamp and restart at `_000` while the same live session continues.

## Rules

1. Group identical creator and run timestamp first.
2. Order each run by numeric suffix.
3. If MP4 and TS share the same stem, select a valid MP4 and retain TS only as fallback.
4. Estimate run end from probed durations. If probing fails, use 30 minutes per completed split and flag the estimate.
5. Merge adjacent runs for the same creator when the next run starts within the configured reconnect gap after the previous estimated end.
6. Do not merge only because two runs occur on the same date. Surface uncertain merges for review.
7. Preserve the source list and offsets so timestamps can be mapped back to individual files.

Never concatenate or delete recordings during discovery. Transcribe files separately and combine timestamp metadata logically; this allows retrying a damaged split without rebuilding the session.

