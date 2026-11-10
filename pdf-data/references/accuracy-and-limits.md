# 准确性与已知限制

## 设计原则

1. **文本层优先**：只读取 PDF 自带的文本层；不做 OCR。
2. **多引擎择优**：PyMuPDF 负责版面与结构，pdfplumber 用于表格补充和文本交叉校验，pypdf 读取元数据、表单与加密权限。
3. **冲突不隐藏**：引擎差异、字体映射异常、扫描页都写入 `warnings[]`，并在 `quality` 中留下可核对的数值。
4. **只读与安全**：不修改 PDF，不执行链接或附件，不爆破密码。

## 阈值与判定

| 机制 | 阈值 | 说明 |
|---|---|---|
| 文本层判定 | 归一化字符数 ≥ 10 | 少于 10 记为 `text_layer=false` |
| 扫描页判定 | 字符数 < 10 且图片覆盖率 ≥ 0.8 | 同时给 `NO_TEXT_LAYER` 与 `scanned` |
| 全扫描文档 | 所选页全部无文本层 | `SCANNED_PDF`，退出码 4 |
| 文本交叉校验 | 字符数差比 > 0.15 或 token Jaccard < 0.80 | 标记 `TEXT_MISMATCH` |
| 小文本交叉校验 | 两侧字符数 < 10 | 直接比较是否完全一致 |
| 表格同表判定 | 旋转为 0 且 bbox IoU ≥ 0.5，或单元格矩阵完全一致 | 同表保留 PyMuPDF 结果 |
| 表格有效性 | ≥ 2 行、≥ 2 列、非空单元 ≥ 60% | 仅用于采纳 pdfplumber 独有的表 |
| 表格去重 | 同引擎 bbox IoU ≥ 0.8 | 避免重复输出 |
| 页眉页脚 | 页面数 ≥ 3 且同 key 出现比例 ≥ 0.60 | 仅分析已选页面；短文档不剥离 |
| 分栏 | 中间 80% 宽度出现 ≥ 8pt 空白带，两侧各 ≥ 15% 词且各 ≥ 3 行 | 最多识别 3 栏；置信度 < 0.7 时回退坐标排序 |
| 大文档 | > 200 页或 > 200MB | 交叉校验最多抽样 20 页 |
| 图片导出上限 | 单图 > 20MB | 跳过并给 `IMAGE_LIMIT` |

## 坐标系

- 所有 bbox 与字级坐标位于 **PyMuPDF 未旋转页面坐标系**（`coordinate_space: mupdf_unrotated_top_left`），原点左上，单位 point（1/72 英寸）。
- 页面宽高 `width` / `height` 是包含 `/Rotate` 的显示尺寸；旋转页上二者可能与未旋转坐标系宽高互换。
- **旋转页禁止跨引擎比较 bbox**：pdfplumber 坐标位于显示坐标系。交叉校验只比较文本；表格同表判定在旋转页仅比较单元格矩阵。

## 文本与阅读顺序

- 双栏/三栏通过垂直空白带识别；全宽块（标题、分节线）作为锚点，栏内按纵向排序。
- 未能识别分栏时按 `(y, x)` 排序，`layout.method` 为 `mupdf_sort`。
- 段落内行拼接：拉丁文行尾 `-` 且下行小写字母开头时合并；CJK 相邻行直接拼接不加空格。
- 连字与全角/半角经 NFKC 归一化（`ﬁ` → `fi`）。
- `word_count` 按空白切分，中文通常偏低，仅作信息字段，不作为质量判据。

## 页眉页脚与页码

- 仅在页面顶部/底部 12% 区域采样，key 归一化时数字替换为 `#`，因此 `Page 1`、`Page 2` 归为同一 key。
- 识别到的行在 `blocks[].lines[]` 上标记 `furniture: true`，整块被标记时 `blocks[].furniture: true`。
- Markdown 默认跳过这些行；JSON 完整保留，并在 `pages[].headers_footers` 汇总原文与 bbox。
- 短文档（少于 3 页）不剥离，避免误删姓名、联系方式等首屏内容。

## 表格

- `auto`：先跑 PyMuPDF `find_tables(strategy="lines")`；若 pdfplumber 已因交叉校验打开，则用其表格补充与比对。
- `--table-strategy pdfplumber`：完全使用 pdfplumber 表格（对无框线、对齐型表格有时更好）。
- `off`：不提取表格，正文仍保留文本块。
- 表格单元格文本不会在 Markdown 正文重复渲染（中心落入表格 bbox 的块会被跳过）。
- 无框线、跨页表、合并单元格、嵌套表格可能不完整，需要人工复核。

## 不支持或不可靠的场景

| 场景 | 表现 | 建议 |
|---|---|---|
| 扫描件 / 纯图片页 | `text_layer=false`，退出码 4（全部页） | 本 skill 不做 OCR；改用 OCR 工具后重新提取 |
| 字体缺 ToUnicode | `(cid:N)`、乱码、`CID_GLYPHS` | 文本不可靠，需换字体或 OCR |
| 艺术字 / 曲线文本 | 可能提取不到 | 视为图片处理，需 OCR |
| RTL（阿拉伯语/希伯来语） | 阅读顺序未专门处理 | 人工复核 |
| XFA 动态表单 | 字段可能缺失 | 使用 Acrobat/专业库，或人工核对 |
| 加密且无密码 | 退出码 3 | 让用户提供显式密码；不爆破 |
| 损坏 PDF | 退出码 2 | 先修复文件 |
| 超大文档 | 交叉校验抽样 | `--no-crosscheck` 或分页处理 |

## 依赖缺失时的降级

| 缺失 | 影响 | 输出 |
|---|---|---|
| PyMuPDF | 无法提取 | 退出码 2，提示安装 |
| pdfplumber | 无交叉校验、无 pdfplumber 表格补充 | `OPTIONAL_DEP_MISSING`；表格仅 PyMuPDF |
| pypdf | 元数据/表单/权限识别退化 | PyMuPDF 元数据、widgets、embfile 兜底 |

## 质量复核建议

1. 先看 `warnings` 与 `extraction.crosscheck.mismatched_pages`。
2. 文本字段与 `pages[].text` 对照；不要只依赖 Markdown 的排版结果。
3. 表格引用前核对 `tables[].rows` 与 `cross_check`。
4. 简历字段缺失时检查 `blocks` 中是否被识别为页眉页脚；必要时用 `--keep-headers` 重跑。
5. 扫描页、CID 页、RTL 页不要直接交付结构化字段，先向用户说明限制。
