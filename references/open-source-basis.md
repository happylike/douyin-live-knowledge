# Open-source basis

This skill was designed after reviewing these MIT-licensed projects:

- `imlewc/video-to-subtitle-summary-skill`, reviewed at commit `50598e25e9962b3f7fef3c7d73c066c00d3ecb87`. Adopted concepts: local-file mode, timestamped SRT plus plain text, selectable local ASR backends, and explicit handling of transcription errors.
- `ml-explore/mlx-examples` Whisper implementation. Adopted concept: use MLX Whisper on Apple Silicon and retain segment timestamps.
- `jftuga/transcript-critic`. Adopted concept: separate key concepts, evidence/limitations, and underdeveloped areas in transcript analysis.

The scripts in this skill are newly implemented for session reconstruction, structured analysis interchange, and Obsidian output. If future updates copy substantial upstream code, retain the upstream copyright and MIT notice with that code.

