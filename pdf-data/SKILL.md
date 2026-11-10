---
name: pdf-data
version: "1.0.0"
author: "bucai2417"
display_name: "PDF 数据提取"
display_name_en: "PDF Data Extraction"
description: "Extract complete, accurate data from PDF files with Python: page text in reading order, per-page layout and coordinates, tables, links, metadata, outline, form fields, attachments, and image metadata, written as structured JSON plus clean Markdown. Use when the user asks to read, parse, inspect, or convert a PDF, extract a PDF resume or document into fields, pull tables from a PDF, turn a PDF into Markdown or JSON, or analyze PDF metadata and links. 用 Python 读取 PDF 并全面准确提取数据：逐页文本与阅读顺序、版面与坐标、表格、链接、元数据、目录、表单、附件、图片元数据，输出结构化 JSON 与可直接阅读的 Markdown。当用户要求读取、解析、提取 PDF，把 PDF 简历或文档转成字段或表格，PDF 转 Markdown/JSON，或检查 PDF 元数据与链接时使用。不适用于扫描件 OCR（仅检测并警告）、PDF 生成、编辑、合并或拆分。"
description_zh: "用 Python 读取 PDF 并全面准确提取数据：逐页文本与阅读顺序、版面与坐标、表格、链接、元数据、目录、表单、附件、图片元数据，输出结构化 JSON 与可直接阅读的 Markdown。当用户要求读取、解析、提取 PDF，把 PDF 简历或文档转成字段或表格，PDF 转 Markdown/JSON，或检查 PDF 元数据与链接时使用。不适用于扫描件 OCR（仅检测并警告）、PDF 生成、编辑、合并或拆分。"
description_en: "Extract complete, accurate data from PDF files with Python: page text in reading order, per-page layout and coordinates, tables, links, metadata, outline, form fields, attachments, and image metadata, written as structured JSON plus clean Markdown. Use when the user asks to read, parse, inspect, or convert a PDF, extract a PDF resume or document into fields, pull tables from a PDF, turn a PDF into Markdown or JSON, or analyze PDF metadata and links. Not for OCR of scanned PDFs (detection and warning only), PDF generation, editing, merging, or splitting."
metadata:
  scope: "document-processing"
  languages: "en,zh"
---

# PDF 数据提取 / PDF Data Extraction

> 只读解析 PDF，输出结构化 JSON 与阅读顺序 Markdown；不做 OCR，不修改输入文件。

## 何时使用（触发场景）

只要任务涉及下面任一情况，就使用本 skill：

- **读取/解析 PDF**：读取、解析、提取、分析、检查、搜索 PDF 内容。
- **简历与文档**：PDF 简历、合同、报告、论文、发票、说明书、通知。
- **结构化提取**：把 PDF 转成 JSON/字段/表格，提取姓名、联系方式、教育、经历、项目、技能、金额、日期。
- **格式转换**：PDF 转 Markdown、纯文本（保留阅读顺序）。
- **文档要素**：PDF 元数据、目录/大纲、超链接、表单字段、附件、图片元数据、页码与页眉页脚。
- **批量处理**：批量抽取多个 PDF，或对比多个 PDF 的文本与表格。

即使对方只说“帮我看看这个 PDF”“把这个简历读一下”，也按本 skill 执行。

## 不适用（边界）

- **扫描件 OCR**：图片型 PDF 只检测并警告（`NO_TEXT_LAYER` / `SCANNED_PDF`，退出码 4），不提供字符识别。
- **生成/编辑 PDF**：创建、修改、合并、拆分、签名、加水印请用其他工具。
- **密码爆破**：只接受显式 `--password`，不做字典或暴力尝试。

## 依赖与安装

```bash
python -m pip install "pymupdf>=1.23" "pdfplumber>=0.10" "pypdf>=4.0"
```

- **PyMuPDF（必需）**：文本层、版面、字级坐标、表格、图片元数据、链接。
- **pdfplumber**：表格补充与文本交叉校验；缺失时自动降级并给 `OPTIONAL_DEP_MISSING` 警告。
- **pypdf**：元数据、表单、owner/user 密码识别；缺失时用 PyMuPDF 兜底。
- Python 3.9+。Windows 控制台若乱码，先设 `PYTHONUTF8=1`（脚本本身已强制 UTF-8 输出）。

## 快速开始

```bash
# 默认：输出到 ./pdfdata_out/<文件名>/document.json + document.md
python <skill-path>/scripts/extract.py 简历.pdf

# 指定输出目录与格式
python <skill-path>/scripts/extract.py 简历.pdf --out-dir out --format both

# 只取部分页（1 基，支持区间与逗号）
python <skill-path>/scripts/extract.py 报告.pdf --pages 1-3,5

# 直接拿 JSON 到 stdout，不写文件
python <skill-path>/scripts/extract.py 简历.pdf --stdout --format json

# 加密 PDF（只接受显式密码）
python <skill-path>/scripts/extract.py 加密.pdf --password 1234

# 关闭 pdfplumber 交叉校验以提速
python <skill-path>/scripts/extract.py 大文件.pdf --no-crosscheck
```

## CLI 速查

| 参数 | 说明 |
|---|---|
| `INPUT.pdf` | 必填，输入 PDF |
| `--out-dir` | 输出目录，默认 `./pdfdata_out/<stem>/` |
| `--format both\|json\|md\|text` | 默认 `both`；`text` 写 `document.txt` |
| `--pages 1-3,5` | 1 基页码；越界部分裁剪并警告，全部越界退出 2 |
| `--password` | 加密 PDF 的显式密码 |
| `--table-strategy auto\|mupdf\|pdfplumber\|off` | 默认 `auto`（PyMuPDF 为主，pdfplumber 补充/校验） |
| `--images none\|meta\|extract` | 默认 `meta`；`extract` 写 `images/` |
| `--keep-headers` | 保留页眉页脚到 Markdown 正文（JSON 始终保留） |
| `--char-coords` | 增加字级 bbox，JSON 体积明显变大 |
| `--no-crosscheck` | 关闭 PyMuPDF/pdfplumber 文本交叉校验 |
| `--stdout` | 只输出选定格式，不写文件；`format=both` 时输出 JSON |

退出码：`0` 成功（可有警告）；`1` 内部异常；`2` 参数/文件/损坏/零页/页码错误；`3` 加密且无有效密码；`4` 所选页面全部无文本层（仍写出带警告的产物）。

## 输出说明

**JSON（`document.json`，schema v1）**

- `source`：路径、文件名、大小、SHA-256。
- `document`：页数、是否加密、`access`（none/user/owner）、元数据、目录、全文档链接、表单字段、附件、引擎版本。
- `pages[]`：`number`、宽高、旋转、`coordinate_space`、`text_layer`、字符/词数、`layout`（栏数/分栏位置/方法/置信度）、`quality`（flags、CID、替换字符、图片覆盖率、交叉校验）、`blocks`（行与 span、bbox、页眉页脚标记）、`text`、`tables`（行列、bbox、单元 bbox、引擎与交叉校验）、`links`、`images`、`headers_footers`。
- `warnings[]`：`code`、页码、说明。
- `extraction`：生成时间、耗时、选项、计数、交叉校验汇总。

**Markdown（`document.md`）**

标题与元数据 → 警告摘要 → 目录 → 每页正文（标题层级、段落、表格、链接）→ 页脚；页眉页脚默认剥离，`--keep-headers` 可保留。

**纯文本（`document.txt`）**：按阅读顺序的文本与 TSV 表格，无 Markdown 标记。

## 质量标志解读

| code | 含义 | 建议 |
|---|---|---|
| `NO_TEXT_LAYER` | 某页文本层缺失或过少 | 检查是否扫描页；本工具不 OCR |
| `SCANNED_PDF` | 所选页全部无文本层 | 明确告知用户这是扫描版 PDF |
| `TEXT_MISMATCH` | PyMuPDF 与 pdfplumber 文本差异大 | 对照 `quality.crosscheck`，必要时检查字体映射 |
| `TABLE_MISMATCH` | 表格交叉校验不一致 | 默认保留 PyMuPDF 结果；可换 `--table-strategy pdfplumber` |
| `CID_GLYPHS` | 存在 `(cid:)` 字形 | 字体缺 ToUnicode，文本可能不完整 |
| `REPLACEMENT_CHARS` | 存在 U+FFFD | 编码异常，引用时不要臆补 |
| `FURNITURE_STRIPPED` | 重复页眉/页脚/页码已从 Markdown 移除 | JSON `headers_footers` 保留原文 |
| `OPTIONAL_DEP_MISSING` | 可选依赖缺失 | 按提示 `pip install` 后重跑 |
| `PAGE_RANGE_CLIPPED` | 页码部分越界 | 已自动裁剪 |
| `LARGE_DOCUMENT` | 页数或体积较大 | 交叉校验抽样执行；可用 `--no-crosscheck` |
| `IMAGE_LIMIT` | 单图超过 20MB 未导出 | 需要时单独处理 |
| `PASSWORD_OWNER` | 使用 owner 密码打开 | 权限更宽，注意说明 |

## 简历 / 文档工作流

1. 先读 `document.md` 获得整体结构与阅读顺序。
2. 用 `document.json` 的 `pages[].text`、`metadata`、`links`、`tables` 取字段。
3. 页眉页脚默认不进 Markdown；需要时读 `pages[].headers_footers`。
4. 表格在 `pages[].tables`，Markdown 中另有 pipe 表；表格内文字不会在正文重复渲染。
5. 出现 `NO_TEXT_LAYER` / `SCANNED_PDF` 时，直接告诉用户该页是图片型、未 OCR，不要编造字段。
6. 字段缺失或交叉校验不一致时，以警告为准做人工复核，不要凭空猜测。

## 必守不变量

- [ ] 只读解析：不修改输入 PDF，不执行链接、不打开附件。
- [ ] 不爆破密码；只使用调用方显式提供的 `--password`。
- [ ] 不伪造结果：缺失字段、扫描页、引擎冲突都如实报告。
- [ ] 扫描件不 OCR，只检测与警告。
- [ ] JSON 保留原始页眉页脚、坐标与表格；Markdown 默认清洁。
- [ ] 输出 UTF-8、换行 `\n`，写文件使用原子替换。
- [ ] 图片文件名只由页码与序号生成，不信任 PDF 内部名称。

## 参考文件路由

| 文件 | 何时读 |
|---|---|
| `references/output-schema.md` | 需要完整字段表、枚举、JSON 示例时 |
| `references/accuracy-and-limits.md` | 需要质量阈值、坐标系、跨引擎差异、已知限制时 |
| `references/recipes.md` | 简历字段映射、批量处理、jq 查询、表格导出 CSV |

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 退出码 3 | 加密 PDF 无有效密码 | 让用户提供密码后用 `--password` |
| 退出码 4 | 所选页全部无文本层 | 说明是扫描件；需要识别请另用 OCR 工具 |
| 某些页 `text_layer=false` | 扫描页或纯图片页 | 查看 `quality.image_coverage` 与警告 |
| 表格缺失 | 无框线或识别线策略不适用 | 试 `--table-strategy pdfplumber`，或接受无表格结构 |
| 中文/特殊字符乱码 | 字体缺 ToUnicode 映射 | 看 `CID_GLYPHS` / `REPLACEMENT_CHARS` 警告 |
| 处理很慢 | pdfplumber 交叉校验开销 | 用 `--no-crosscheck` 或 `--pages` 限定范围 |
| 页眉或页码“消失” | 被识别为重复家具并从 Markdown 移除 | 用 `--keep-headers`，或从 JSON `headers_footers` 读取 |
| Windows 控制台乱码 | 终端 GBK | 设 `PYTHONUTF8=1`；写文件本身为 UTF-8 |

安装位置：`~/.Claud/skills/pdf-data/`（Claud / Claud Code），或对应 agent 的 skills 目录。

*版本 1.0.0 · 作者 bucai2417 · 最后更新 2026-11-10*
