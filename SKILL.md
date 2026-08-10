---
name: douyin-live-knowledge
description: 将本地抖音直播视频或音频重建为完整直播场次，生成带时间戳的中文文字稿，为每个连线案件附上该案完整原始文字稿，提炼实务知识和有价值的唠嗑，并输出全中文属性、中文目录及七个 Bases 看板的 Obsidian 知识库。适用于 .mp4、.ts、.mov、.mkv、.m4a、.mp3 文件或录制目录，尤其适合律师、咨询和答疑类直播的转写、总结、案件库建设、知识复用及发布到 Obsidian。
---

# 抖音直播知识库

把一场直播作为母记录。完整文字稿、连线案件、实务知识和唠嗑价值都必须能追溯到该场直播和原视频时间位置。

## 强制执行顺序

1. 只读扫描源文件。目录输入先运行 `scripts/scan_recordings.py`；同名 MP4 与 TS 优先有效 MP4，但不删除任何源文件。
2. 按主播、录制时间和分段编号重建场次。读取 `references/session-reconstruction.md`；不要仅因同一天录制就合并。
3. 先征得用户同意，再安装运行时或下载模型。Apple Silicon 生产转写默认使用持久化的 `whisper-large-v3-turbo`；小模型只用于冒烟测试。不得把敏感录音上传云端，除非用户明确选择。
4. 每个分段单独转写，保留时间戳与置信信息。跨多个录制分段时运行 `scripts/merge_session_transcripts.py`，生成一份整场累计时间文字稿。
5. 读取 `references/analysis-schema.md`。涉及法律或敏感咨询时还必须读取 `references/privacy-and-quality.md`。按结构生成分析 JSON。
6. 运行 `scripts/validate_analysis.py`，修复全部错误。不得用未经校验的分析生成正式笔记。
7. 运行 `scripts/render_obsidian.py`，输出到暂存知识库根目录；程序必须自动建立主播一级大文件夹，并按每条案件的全部 `sourceRanges` 在案件笔记末尾附加“本案完整文字稿”。不得直接写正式 Vault。
8. 对生成的主播目录运行 `scripts/validate_obsidian_output.py`，检查中文属性、目录、双链、七个 Bases、业务关联，以及每份案件笔记的完整文字稿章节、片段数量和敏感标记。
9. 检查暂存结果，向用户报告数量、低置信内容、法律核验项和隐私状态。只有用户确认后才能写入正式 Vault。
10. 重跑时用稳定编号更新原笔记，禁止重复创建同一场次、案件或知识卡片。

## 转写运行时

- 安装持久化运行时：用户同意后运行 `python scripts/install_runtime.py --backend auto`。
- Apple Silicon 默认模型目录：`~/.cache/douyin-live-knowledge/models/whisper-large-v3-turbo`。
- Hugging Face 大文件通道失败：用户同意后运行 `scripts/download_mlx_model.py` 断点续传。
- 生产转写必须指定中文和法律领域提示词，并保留 JSON；纯文本不能作为唯一档案。
- Codex 负责调度本地转写程序，本身不应声称直接听懂音频。
- 当前工作流不做说话人声纹分离。可以按语义判断案件边界，但完整文字稿不得伪造逐句说话人标签。

## 分析原则

- 一位连线人的一个独立事项是一条案件；断线重连或跨30分钟分段仍使用同一案件编号和多个来源时间段。
- 每份案件笔记除概括性内容外，末尾必须附该案全部来源时间段对应的逐段时间戳原始文字稿。断线续接按多个 `sourceRanges` 分节，不得把两次连线之间的无关内容夹入案件原稿。
- 分开记录咨询人陈述、具体问题、主播分析、主播回答、处理步骤、证据、期限和风险。
- 主播观点必须写成“主播认为”或“主播建议”，不能改写成已核验法律结论。
- 每条案件、知识和唠嗑价值按1至5级标重要度，并保存来源时间。
- 纯寒暄留在完整文字稿和时间轴；只有具备沟通、情绪支持、人情世故、职业或生活经验价值的闲聊才建立唠嗑卡片。
- 案件的概括、字段和关键原话必须脱敏；案件末尾的完整原稿与整场完整文字稿都必须标记“含敏感原文”，且不得把正文放入宽泛看板属性。

## Obsidian 输出契约

读取 `references/obsidian-data-model.md`。先按主播建立一级大文件夹，再在主播目录中严格生成：

- `直播场次`：每场一份母记录。
- `完整文字稿`：每场一份一对一整场稿。
- `连线案件`：每个独立连线事项一份，正文末尾必须包含该案完整时间戳文字稿。
- `实务知识`：每个可跨案件复用的知识点一份。
- `唠嗑价值`：每段值得复用的非案件交流一份。
- `_系统数据`：分析 JSON、文字稿 JSON 和处理清单。

目录必须是 `抖音直播知识库/主播名/业务文件夹`。不同主播不得共用同一组业务文件夹或 Bases；同一主播的多场直播统一进入该主播目录。知识库根目录只保存主播总入口。

所有用户可见的文件夹、标题、属性名、属性值、表头、视图名和状态必须使用中文。模型名称、文件扩展名以及 Obsidian `.base` 必需语法可以保留原始标识。机器分析 JSON 的内部字段可以保留英文，但不得泄漏为 Obsidian 用户属性。

七个看板固定为：`📺 直播场次.base`、`📝 完整文字稿.base`、`⚖️ 连线案件.base`、`💡 实务知识.base`、`☕ 唠嗑价值.base`、`🔎 待复核.base`、`📊 数据总表.base`。

## 常用命令

```bash
python scripts/scan_recordings.py /录制目录 --output manifest.json

python scripts/transcribe_media.py /视频.mp4 \
  --output-dir /暂存/分段000 --backend auto --language zh

python scripts/merge_session_transcripts.py /暂存/分段000/transcript.json /暂存/分段001/transcript.json \
  --场次编号 主播-YYYYMMDD-HHMMSS --主播 主播名 --输出前缀 /暂存/整场完整文字稿

python scripts/validate_analysis.py /暂存/整场分析.json

python scripts/render_obsidian.py \
  --analysis /暂存/整场分析.json --transcript /暂存/整场完整文字稿.json \
  --output-root /暂存/抖音直播知识库 --vault-folder 抖音直播知识库

python scripts/validate_obsidian_output.py /暂存/抖音直播知识库/主播名
```

## 按需读取

- 场次跨分段或断线重连：读取 `references/session-reconstruction.md`。
- 编写分析 JSON：读取 `references/analysis-schema.md`。
- 法律、隐私或质量复核：读取 `references/privacy-and-quality.md`。
- 设计或检查 Obsidian：读取 `references/obsidian-data-model.md`。
- 更新模型、后端或开源归属：读取 `references/open-source-basis.md`。
