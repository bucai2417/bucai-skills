# 常用做法

## 1. 读取 PDF 简历并提取字段

```bash
python scripts/extract.py 简历.pdf --out-dir out --format both
```

先读 `out/document.md` 了解结构，再从 `out/document.json` 取字段：

```python
import json
from pathlib import Path

data = json.loads(Path("out/document.json").read_text(encoding="utf-8"))
text = "\n".join(page["text"] for page in data["pages"])
meta = data["document"]["metadata"]
links = [link["uri"] for link in data["document"]["links"] if link.get("uri")]
tables = [table for page in data["pages"] for table in page["tables"]]

print("姓名候选：", text.splitlines()[0] if text else "")
print("邮箱/链接：", links)
print("标题：", meta.get("title"))
print("表格数：", len(tables))
```

工作流建议：

1. 检查 `warnings`，遇到 `NO_TEXT_LAYER` / `SCANNED_PDF` 立即告知用户该页未 OCR。
2. 姓名、联系方式通常在首个文本块或链接中；经历/教育常在表格或分段中。
3. 页眉页脚被剥离时，正文更干净；需要页码或页眉信息时读 `headers_footers`。
4. 不要用正则硬套所有简历；以 JSON 的分块与表格为准。

## 2. 提取表格并导出 CSV

```bash
python scripts/extract.py 报告.pdf --out-dir out --table-strategy pdfplumber
```

```python
import csv, json
from pathlib import Path

data = json.loads(Path("out/document.json").read_text(encoding="utf-8"))
rows = []
for page in data["pages"]:
    for table in page["tables"]:
        for row in table["rows"]:
            rows.append(row)

with open("tables.csv", "w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerows(rows)
```

注意：同一表格可能因跨页被拆成多个 `tables[]` 项；需要时按 `bbox` 与表头人工合并。

## 3. jq 查询示例

```bash
# 标题与作者
jq '.document.metadata | {title, author}' out/document.json

# 所有警告
jq '.warnings[] | {code, page_index, message}' out/document.json

# 每页质量摘要
jq '.pages[] | {number, text_layer, chars: .char_count, flags: .quality.flags}' out/document.json

# 所有表格
jq '[.pages[].tables[] | {engine, rows}]' out/document.json

# 所有链接
jq '[.document.links[] | select(.uri) | .uri]' out/document.json
```

## 4. 批量处理

```bash
# bash
for f in pdfs/*.pdf; do
  name=$(basename "$f" .pdf)
  python scripts/extract.py "$f" --out-dir "out/$name" --format both --no-crosscheck
done
```

```powershell
# PowerShell
Get-ChildItem pdfs\*.pdf | ForEach-Object {
  python scripts/extract.py $_.FullName --out-dir ("out\" + $_.BaseName) --format both --no-crosscheck
}
```

批量时建议先对单个样本确认质量，再关闭交叉校验以提速；出现 `TEXT_MISMATCH` 的文件单独复核。

## 5. 只处理指定页

```bash
python scripts/extract.py 年报.pdf --pages 1-3,10 --out-dir out
```

页码 1 基；超出范围的部分会被裁剪并给出 `PAGE_RANGE_CLIPPED`。

## 6. 加密 PDF

```bash
python scripts/extract.py 加密.pdf --password "用户提供的密码"
```

- 空密码与显式密码都会尝试；失败退出码 3。
- `document.access` 为 `user` 或 `owner`；使用 owner 密码会额外给 `PASSWORD_OWNER` 警告。
- 不提供字典/暴力尝试。

## 7. 保留页眉页脚

```bash
python scripts/extract.py 报告.pdf --keep-headers
```

Markdown 会包含页眉、页脚与页码；JSON 始终保留在 `headers_footers` 与 `blocks[].lines[].furniture`。

## 8. 检查扫描页

```bash
python scripts/extract.py 扫描件.pdf --format json --stdout | jq '.pages[] | {number, text_layer, coverage: .quality.image_coverage}'
```

退出码 4 表示全部所选页无文本层；本 skill 不 OCR，需要识别时先做 OCR 再提取。

## 9. 导出图片

```bash
python scripts/extract.py 图册.pdf --images extract --out-dir out
```

图片写入 `out/images/`，文件名只包含页码与序号；单图超过 20MB 会跳过并给 `IMAGE_LIMIT`。图片本身不做 OCR。
