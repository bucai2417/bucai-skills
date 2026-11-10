# PDF 数据提取 / PDF Data Extraction

一个用于 Claud Code / Codex / Agent Skills 的通用 skill：用 Python 只读解析 PDF，全面、准确地提取文本、版面、表格、链接、元数据、目录、表单、附件与图片元数据，并输出结构化 JSON 与阅读顺序 Markdown。适用于 PDF 简历、合同、报告、论文等文档。

## 特性

- **多引擎择优**：PyMuPDF 负责文本层、版面与字级坐标；pdfplumber 补充表格并做文本交叉校验；pypdf 读取元数据、表单与加密权限。
- **阅读顺序**：识别双栏/三栏版面，按栏内纵向顺序重建段落；单栏回退到坐标排序。
- **表格**：PyMuPDF 优先，pdfplumber 补充与比对，冲突时保留 PyMuPDF 并给出警告。
- **文档要素**：元数据、目录、超链接、表单字段、附件、图片元数据、页眉页脚/页码。
- **质量信号**：无文本层、扫描件、`(cid:)` 字形、替换字符、引擎文本差异、表格差异，统一进入 `warnings`。
- **安全**：只读解析，不执行链接或附件，不爆破密码。
- **无 OCR**：扫描件只检测并明确警告，不做字符识别。

## 环境要求

- Python 3.9+
- `pymupdf>=1.23`（必需）
- `pdfplumber>=0.10`、`pypdf>=4.0`（可选，缺失时自动降级）

```bash
python -m pip install "pymupdf>=1.23" "pdfplumber>=0.10" "pypdf>=4.0"
```

## 快速开始

```bash
python scripts/extract.py 简历.pdf
# -> ./pdfdata_out/简历/document.json
# -> ./pdfdata_out/简历/document.md

python scripts/extract.py 简历.pdf --out-dir out --format both
python scripts/extract.py 报告.pdf --pages 1-3,5
python scripts/extract.py 简历.pdf --stdout --format json
python scripts/extract.py 加密.pdf --password 1234
```

## 输出

| 文件 | 内容 |
|---|---|
| `document.json` | schema v1：源文件摘要、文档元数据、目录、链接、表单、附件、逐页块/文本/表格/图片/页眉页脚、质量信号、警告、提取统计 |
| `document.md` | 标题、元数据、警告摘要、目录、逐页正文与 pipe 表格、链接、页脚 |
| `document.txt` | 按阅读顺序的纯文本与 TSV 表格（`--format text`） |
| `images/` | `--images extract` 时导出图片，文件名由页码与序号生成 |

字段与枚举详见 `references/output-schema.md`；质量阈值与限制见 `references/accuracy-and-limits.md`。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（可能带警告） |
| 1 | 未预期的内部错误（`PDFDATA_DEBUG=1` 打印堆栈） |
| 2 | 参数、文件、损坏、零页或页码错误 |
| 3 | 加密 PDF 且无有效密码 |
| 4 | 所选页面全部无文本层（仍写出带警告的产物） |

## 测试

```bash
python tests/test_extract.py
```

测试样本由 PyMuPDF 在临时目录动态生成，覆盖英文、中文、双栏、表格、图片/扫描页、加密、元数据/大纲/链接、页眉页脚、旋转页、页码选择、损坏/零页、stdout、交叉校验开关等。

## 打包发布

```bash
python ../package_skill.py --src . --check-only
python ../package_skill.py --src . --out ../dist
```

## 限制

- 不做 OCR；图片型 PDF 只报告无文本层。
- 复杂排版（艺术字、曲线文本、RTL、XFA 表单）可能提取不全，以 `warnings` 与质量为信号。
- 表格识别依赖 PDF 中的线或文本对齐；无框线表格可能需要 `--table-strategy pdfplumber` 或人工复核。
- 旋转页的坐标位于未旋转坐标系，跨引擎比较仅使用文本，不比较 bbox。

## 许可证

MIT
