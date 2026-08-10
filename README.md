# Douyin Live Knowledge

一个面向 Codex 的本地抖音直播知识库 Skill。它把分段录制的视频或音频重建为完整直播场次，生成带时间戳的中文文字稿，切分连线案件、实务知识和有价值的唠嗑，并输出可直接放入 Obsidian 的中文知识库与七个 Bases 看板。

本项目特别适合律师、咨询、答疑等包含大量连线内容的直播归档。每份案件笔记除了结构化概括，还会在末尾附上该案件全部来源时间段对应的完整机器识别文字稿。

## 主要能力

- 扫描 `.mp4`、`.ts`、`.mov`、`.mkv`、`.m4a`、`.mp3` 等本地录制文件。
- 按主播、录制时间和分段编号重建直播场次。
- 识别断线重连和跨录制分段的同一场直播。
- 使用 MLX Whisper 或 faster-whisper 进行本地中文转写。
- 合并分段时间轴，保留整场时间、分段时间和来源文件。
- 将一场直播切分为多个独立连线案件。
- 为每个案件附加完整时间戳原稿；断线续接按多个来源区段分节，不夹入中间无关内容。
- 提炼可跨案件复用的实务知识和具备实际价值的非案件交流。
- 生成全中文目录、属性、状态和七个 Obsidian Bases 看板。
- 校验分析结构、中文属性、双链、案件文字稿片段数量及隐私标记。

## 工作方式

这是一个由 Codex 调度的 Skill，不是单独运行一个命令即可完成全部语义分析的应用。Codex 负责依次调用项目脚本、阅读带时间戳的文字稿、生成结构化分析 JSON、执行校验，并在用户确认后发布到正式 Vault。

```text
本地录制文件
  ↓ 扫描与场次重建
分段转写 JSON
  ↓ 合并时间轴
整场完整文字稿
  ↓ Codex 语义分析与案件切分
分析 JSON
  ↓ 校验与渲染
Obsidian 暂存知识库
  ↓ 用户确认
正式 Vault
```

## 安装

将仓库克隆到 Codex 的 Skills 目录：

```bash
git clone https://github.com/happylike/douyin-live-knowledge.git \
  ~/.codex/skills/douyin-live-knowledge
```

更新已有安装：

```bash
git -C ~/.codex/skills/douyin-live-knowledge pull --ff-only
```

安装完成后，可以在任务中这样调用：

```text
使用 $douyin-live-knowledge 整理这个本地抖音直播录制目录，
先输出到暂存目录，检查通过后再询问是否写入正式 Vault。
```

## 转写运行时

运行时安装会创建独立虚拟环境，不污染项目目录：

```bash
python scripts/install_runtime.py --backend auto
```

- Apple Silicon 默认选择 `mlx-whisper`。
- 其他平台默认选择 `faster-whisper`。
- `imageio-ffmpeg` 提供独立 FFmpeg；系统已有 FFmpeg 时也可以直接使用。
- 生产转写默认使用 `whisper-large-v3-turbo`，首次使用可能需要下载较大的模型文件。

安装依赖或下载模型会访问网络，应先得到录音所有者同意。直播原始文件默认只在本地处理。

## 基本流程

### 1. 扫描录制目录

```bash
python scripts/scan_recordings.py /录制目录 --output /暂存/manifest.json
```

同名 MP4 与 TS 会优先选择有效 MP4，但不会删除任何源文件。

### 2. 转写每个录制分段

```bash
python scripts/transcribe_media.py /视频.mp4 \
  --output-dir /暂存/分段000 \
  --backend auto \
  --language zh
```

每个分段会输出 JSON、SRT、Markdown 和纯文本，其中 JSON 是后续处理的主要档案。

### 3. 合并整场文字稿

```bash
python scripts/merge_session_transcripts.py \
  /暂存/分段000/transcript.json \
  /暂存/分段001/transcript.json \
  --场次编号 主播-YYYYMMDD-HHMMSS \
  --主播 主播名 \
  --输出前缀 /暂存/整场完整文字稿
```

### 4. 生成并校验分析 JSON

Codex 按照 [`references/analysis-schema.md`](references/analysis-schema.md) 分析整场文字稿，然后执行：

```bash
python scripts/validate_analysis.py /暂存/整场分析.json
```

分析文件必须通过校验后才能生成正式笔记。

### 5. 渲染 Obsidian 知识库

```bash
python scripts/render_obsidian.py \
  --analysis /暂存/整场分析.json \
  --transcript /暂存/整场完整文字稿.json \
  --output-root /暂存/抖音直播知识库 \
  --vault-folder 抖音直播知识库
```

### 6. 校验输出

```bash
python scripts/validate_obsidian_output.py \
  /暂存/抖音直播知识库/主播名
```

校验器会检查目录、中文属性、稳定编号、双链、七个 Bases、案件完整文字稿章节、片段数量和敏感标记。

## Obsidian 输出结构

```text
抖音直播知识库/
├── 首页.md
└── 主播名/
    ├── 首页.md
    ├── 直播场次/
    ├── 完整文字稿/
    ├── 连线案件/
    ├── 实务知识/
    ├── 唠嗑价值/
    ├── _系统数据/
    ├── 📺 直播场次.base
    ├── 📝 完整文字稿.base
    ├── ⚖️ 连线案件.base
    ├── 💡 实务知识.base
    ├── ☕ 唠嗑价值.base
    ├── 🔎 待复核.base
    └── 📊 数据总表.base
```

不同主播使用各自独立的业务目录和 Bases；同一主播的多场直播进入同一个主播目录。

## 案件完整文字稿

每份案件笔记包含两层内容：

1. 已脱敏的案件事实、问题、分析、回答、处理步骤、证据、期限和风险概括。
2. 按案件全部 `sourceRanges` 摘录的完整机器识别原稿。

如果一次连线断线后重新接入，原稿会按多个来源时间段分别呈现。系统不会简单使用最早开始到最晚结束的大区间，因此不会把两次连线之间的其他案件误收入本案原稿。

## 隐私与法律质量

- 原始媒体、整场文字稿和案件完整原稿可能包含姓名、电话、地址、健康、财务或刑事信息。
- 案件完整原稿会标记为“含敏感原文”，不得通过宽泛看板属性展示正文。
- 对外发布前应再次脱敏，并回到原音视频核对金额、人数、期限、机构名和关键原话。
- 主播观点只能记录为“主播认为”或“主播建议”，不能当作已经核验的法律结论。
- 法条、管辖、时效、责任比例和地域政策等内容应单独标记并人工核验。
- 未经明确授权，不要把敏感录音或文字稿上传到云端服务。

详细规则见 [`references/privacy-and-quality.md`](references/privacy-and-quality.md) 和 [`references/obsidian-data-model.md`](references/obsidian-data-model.md)。

## 项目结构

```text
douyin-live-knowledge/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── obsidian-bases/
├── references/
└── scripts/
```

- [`SKILL.md`](SKILL.md)：Codex 的核心执行规则。
- `scripts/`：扫描、转写、合并、校验和 Obsidian 渲染脚本。
- `references/`：分析结构、隐私质量、场次重建及数据模型说明。
- `assets/obsidian-bases/`：七个中文 Obsidian Bases 模板。

## 开源说明

项目记录了设计时参考的开源基础，详见 [`references/open-source-basis.md`](references/open-source-basis.md)。当前仓库尚未附加开源许可证；公开可见不等于自动授予复制、修改或分发权利。
