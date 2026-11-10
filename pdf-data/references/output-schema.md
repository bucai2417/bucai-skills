# JSON 输出结构（schema v1）

`document.json` 的完整字段说明。所有页码同时存在两种表示：

- `pages[].index`：0 基，供程序使用。
- `pages[].number`：1 基，供人阅读。
- `document.links[].page_index`、`outline[].page_index`：0 基。

## 顶层

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定为 `"1.0"` |
| `source` | object | 源文件信息 |
| `document` | object | 文档级信息 |
| `pages` | array | 逐页结果，顺序与所选页码一致 |
| `warnings` | array | 警告列表 |
| `extraction` | object | 本次提取的元信息 |

## source

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 输入路径（正斜杠） |
| `file_name` | string | 文件名 |
| `size_bytes` | integer | 文件大小 |
| `sha256` | string | 文件 SHA-256 |

## document

| 字段 | 类型 | 说明 |
|---|---|---|
| `page_count` | integer | PDF 总页数 |
| `selected_pages` | integer[] | 本次提取的页码（1 基） |
| `encrypted` | boolean | 是否加密 |
| `access` | string | `none` / `user` / `owner` / `unknown` |
| `metadata` | object | 见下表 |
| `outline` | array | `[{level, title, page_index}]`，`page_index` 可为 null |
| `links` | array | 全文档链接，见 `pages[].links` 并附加 `page_index` |
| `form_fields` | array | `[{name, field_type, value}]` |
| `attachments` | array | `[{name, size_bytes}]` |
| `engines` | object | `{pymupdf, pdfplumber, pypdf}` 版本或 null |

`metadata`：`title`、`author`、`subject`、`keywords`、`creator`、`producer`、`creation_date`、`modification_date`（均为 string 或 null）、`source`（`pypdf` / `fitz`）。

## pages[]

| 字段 | 类型 | 说明 |
|---|---|---|
| `index` / `number` | integer | 0 基 / 1 基页码 |
| `width` / `height` | number | 显示尺寸（含旋转） |
| `rotation` | integer | 页面旋转角 |
| `coordinate_space` | string | 当前固定为 `mupdf_unrotated_top_left`；坐标位于未旋转坐标系 |
| `text_layer` | boolean | 是否有可用文本层（字符数 ≥ 10） |
| `char_count` / `word_count` | integer | 归一化后字符数 / 空白分词数（CJK 词数仅参考） |
| `layout` | object | `{columns, gutter_x, gutters, method, confidence}`；`method` 为 `columns` 或 `mupdf_sort` |
| `quality` | object | 见下表 |
| `blocks` | array | 文本块：`bbox`、`furniture`、`lines[]`（`bbox`、`text`、`spans[]`） |
| `text` | string | 择优后的整页文本（可能来自 PyMuPDF 或 pdfplumber） |
| `tables` | array | 见下表 |
| `links` | array | `[{kind, uri, target_page_index, bbox, label}]`；`kind` 为 `goto/uri/launch/named/gotor/other` |
| `images` | array | `[{id, xref, bbox, width, height, colorspace, bpc, ext, file}]` |
| `headers_footers` | array | `[{zone, text, bbox, is_page_number}]`，`zone` 为 `header/footer` |

### quality

| 字段 | 类型 | 说明 |
|---|---|---|
| `flags` | string[] | `empty_text`、`no_text_layer`、`scanned`、`cid_glyphs`、`replacement_chars`、`control_chars`、`cjk` |
| `char_count` / `word_count` | integer | 与页级字段一致 |
| `text_layer` / `scanned` | boolean | 文本层与扫描判定 |
| `cid_glyphs` | integer | `(cid:N)` 出现次数 |
| `replacement_chars` | integer | U+FFFD 数量 |
| `control_chars` | integer | 非换行/制表控制字符数量 |
| `image_coverage` | number | 图片 bbox 并集覆盖率，0–1 |
| `cjk_ratio` | number | CJK 字符占比 |
| `text_engine` | string | `mupdf` / `pdfplumber` |
| `crosscheck` | object | `{status, char_ratio, jaccard, pdfplumber_char_count}`；`status` 为 `match/mismatch/skipped/unavailable` |

### tables[]

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 页内唯一 ID |
| `engine` | string | `mupdf` / `pdfplumber` |
| `bbox` | number[4] 或 null | `[x0, y0, x1, y1]` |
| `rows` | string[][] | 行优先单元格文本 |
| `cell_bboxes` | array | 行优先扁平单元 bbox，缺失为 null |
| `cross_check` | object | `{status, engine}`；`status` 为 `match/mismatch/unverified` |

### blocks / lines / spans

- `blocks[]`：`bbox`、`furniture`（整块都是页眉页脚时为 true）、`lines[]`。
- `lines[]`：`bbox`、`text`、`furniture`（该行被识别为页眉/页脚/页码时存在）、`spans[]`。
- `spans[]`：`bbox`、`text`、`font`、`size`、`flags`、`color`；`--char-coords` 时增加 `chars[]`（`bbox`、`origin`、`c`）。

## warnings[]

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 固定枚举，见 SKILL.md 质量标志表 |
| `page_index` | integer 或 null | 相关页面（0 基）；文档级警告为 null |
| `message` | string | 人读说明 |

## extraction

| 字段 | 类型 | 说明 |
|---|---|---|
| `generated_at` | string | UTC ISO-8601 |
| `duration_ms` | integer | 耗时 |
| `options` | object | `format`、`pages`、`table_strategy`、`images`、`keep_headers`、`char_coords`、`crosscheck` |
| `counts` | object | `pages`、`chars`、`tables`、`images`、`warnings`、`headers_footers` |
| `crosscheck` | object | `{pages_checked, sampled, mismatched_pages}` |

## 精简示例

```json
{
  "schema_version": "1.0",
  "source": {"path": "C:/docs/a.pdf", "file_name": "a.pdf", "size_bytes": 12345, "sha256": "..."},
  "document": {
    "page_count": 1,
    "selected_pages": [1],
    "encrypted": false,
    "access": "none",
    "metadata": {"title": "简历", "author": null, "subject": null, "keywords": null,
                 "creator": null, "producer": null, "creation_date": null,
                 "modification_date": null, "source": "pypdf"},
    "outline": [{"level": 1, "title": "经历", "page_index": 0}],
    "links": [{"kind": "uri", "uri": "mailto:a@b.com", "target_page_index": null,
              "bbox": [50, 100, 200, 120], "label": "a@b.com", "page_index": 0}],
    "form_fields": [],
    "attachments": [],
    "engines": {"pymupdf": "1.27.2.3", "pdfplumber": "0.11.0", "pypdf": "6.14.2"}
  },
  "pages": [{
    "index": 0, "number": 1, "width": 595.0, "height": 842.0, "rotation": 0,
    "coordinate_space": "mupdf_unrotated_top_left",
    "text_layer": true, "char_count": 120, "word_count": 18,
    "layout": {"columns": 1, "gutter_x": null, "gutters": [], "method": "mupdf_sort", "confidence": 1.0},
    "quality": {"flags": [], "char_count": 120, "word_count": 18, "text_layer": true,
                "scanned": false, "cid_glyphs": 0, "replacement_chars": 0,
                "control_chars": 0, "image_coverage": 0.0, "cjk_ratio": 0.0,
                "text_engine": "mupdf",
                "crosscheck": {"status": "match", "char_ratio": 0.0, "jaccard": 1.0,
                               "pdfplumber_char_count": 120}},
    "blocks": [],
    "text": "张三\n邮箱：a@b.com",
    "tables": [],
    "links": [],
    "images": [],
    "headers_footers": []
  }],
  "warnings": [],
  "extraction": {"generated_at": "2026-11-10T00:00:00Z", "duration_ms": 12,
                 "options": {"format": "both", "pages": [1], "table_strategy": "auto",
                             "images": "meta", "keep_headers": false,
                             "char_coords": false, "crosscheck": true},
                 "counts": {"pages": 1, "chars": 120, "tables": 0, "images": 0,
                            "warnings": 0, "headers_footers": 0},
                 "crosscheck": {"pages_checked": 1, "sampled": false, "mismatched_pages": []}}
}
```
