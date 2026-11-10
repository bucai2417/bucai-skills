#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract PDF text, layout, tables, links, metadata and images to JSON/Markdown.

Usage:
    python scripts/extract.py INPUT.pdf
    python scripts/extract.py INPUT.pdf --out-dir out --format both
    python scripts/extract.py INPUT.pdf --pages 1-3,5 --stdout

Exit codes:
    0 success (warnings may exist)
    1 unexpected internal failure
    2 bad arguments / unreadable / corrupt / zero-page PDF
    3 encrypted PDF without a valid password
    4 every selected page lacks a text layer
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pdfdata import engines, layout, quality, render  # noqa: E402
from pdfdata.engines import (  # noqa: E402
    EncryptedPdfError,
    PlumberSession,
    PdfDataError,
    collect_document_meta,
    open_mupdf,
    optional_dependency_warnings,
    read_page_raw,
)
from pdfdata.model import DocumentResult, Options, PageResult, WarningItem  # noqa: E402

_SAFE_IMAGE_EXT = {
    "png",
    "jpeg",
    "jpg",
    "jpx",
    "gif",
    "tif",
    "tiff",
    "bmp",
    "webp",
    "jbig2",
    "jb2",
    "ccitt",
}
_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_LARGE_PAGES = 200
_LARGE_BYTES = 200 * 1024 * 1024
_CROSSCHECK_SAMPLE = 20


def _reconfigure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _resolve_pages(
    spec: Optional[str], page_count: int
) -> Tuple[List[int], List[WarningItem]]:
    if not spec:
        return list(range(page_count)), []

    parts = [part.strip() for part in spec.split(",") if part.strip()]
    if not parts:
        raise PdfDataError("--pages 不能为空；示例：--pages 1-3,5")

    wanted = set()
    for part in parts:
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", part)
        if not match:
            raise PdfDataError("无效的页码格式：%s（示例：1-3,5）" % part)
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise PdfDataError("无效的页码范围：%s" % part)
        if end - start > 100000:
            raise PdfDataError("页码范围过大：%s" % part)
        wanted.update(range(start, end + 1))

    in_range = sorted(page for page in wanted if 1 <= page <= page_count)
    if not in_range:
        raise PdfDataError("页码超出范围：PDF 共 %d 页" % page_count)

    warnings: List[WarningItem] = []
    dropped = sorted(wanted - set(in_range))
    if dropped:
        warnings.append(
            WarningItem(
                "PAGE_RANGE_CLIPPED",
                "已忽略超出范围的页码：%s" % ",".join(str(page) for page in dropped),
            )
        )
    return [page - 1 for page in in_range], warnings


def _extract_images(
    doc, raw: Dict[str, Any], images_dir: Path, warnings: List[WarningItem]
) -> None:
    for image in raw.get("images", []) or []:
        xref = image.get("xref")
        if not xref:
            continue
        try:
            info = doc.extract_image(int(xref))
        except Exception:
            continue
        data = info.get("image") or b""
        if not data:
            continue
        if len(data) > _IMAGE_MAX_BYTES:
            warnings.append(
                WarningItem(
                    "IMAGE_LIMIT",
                    "第 %d 页图片 %s 超过 20MB，未导出"
                    % (raw["index"] + 1, image.get("id")),
                    raw["index"],
                )
            )
            continue
        extension = str(info.get("ext") or "bin").lower()
        if extension not in _SAFE_IMAGE_EXT:
            extension = "bin"
        name = "p%03d_%s.%s" % (
            raw["index"] + 1,
            str(image.get("id", "img")).split("-")[-1],
            extension,
        )
        try:
            _atomic_write_bytes(images_dir / name, data)
        except OSError:
            continue
        image["ext"] = extension
        image["file"] = "images/" + name


def _image_rects(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return raw.get("images", []) or []


def extract_document(path: Path, opts: Options) -> DocumentResult:
    started = time.time()
    doc = open_mupdf(path, opts.password)
    try:
        page_count = doc.page_count
        selected, range_warnings = _resolve_pages(opts.pages_spec, page_count)
        opts.pages = [index + 1 for index in selected]
        warnings: List[WarningItem] = list(range_warnings)

        for dependency in optional_dependency_warnings():
            warnings.append(
                WarningItem(
                    "OPTIONAL_DEP_MISSING",
                    "未安装 %s，相关能力降级：pip install %s"
                    % (dependency, dependency),
                )
            )

        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0
        if page_count > _LARGE_PAGES or size_bytes > _LARGE_BYTES:
            warnings.append(
                WarningItem(
                    "LARGE_DOCUMENT",
                    "文档较大（%d 页，%.1f MB）；大文档的交叉校验会抽样执行"
                    % (page_count, size_bytes / (1024.0 * 1024.0)),
                )
            )

        if engines.pdfplumber is None and opts.table_strategy == "pdfplumber":
            warnings.append(
                WarningItem(
                    "OPTIONAL_DEP_MISSING",
                    "表格策略 pdfplumber 不可用：未安装 pdfplumber，已回退 PyMuPDF",
                )
            )
            opts.table_strategy = "auto"

        raw_pages: List[Dict[str, Any]] = []
        for index in selected:
            page = doc.load_page(index)
            try:
                raw_pages.append(
                    read_page_raw(page, opts.char_coords, opts.table_strategy)
                )
            except Exception as exc:
                raise PdfDataError("解析第 %d 页失败：%s" % (index + 1, exc))

        furniture = layout.detect_furniture(raw_pages)
        furniture_lines = sum(len(records) for records in furniture.values())
        if furniture_lines:
            warnings.append(
                WarningItem(
                    "FURNITURE_STRIPPED",
                    "识别到 %d 行重复页眉/页脚/页码，已从 Markdown 正文移除；JSON 仍保留原文"
                    % furniture_lines,
                )
            )

        sampled = len(selected) > 50
        if sampled and opts.crosscheck:
            step = max(1, len(selected) // _CROSSCHECK_SAMPLE)
            crosscheck_indexes = set(selected[::step][:_CROSSCHECK_SAMPLE])
        else:
            crosscheck_indexes = set(selected) if opts.crosscheck else set()

        need_plumber = (
            engines.pdfplumber is not None
            and (
                opts.table_strategy == "pdfplumber"
                or (opts.crosscheck and bool(crosscheck_indexes))
            )
        )
        session: Optional[PlumberSession] = None
        if need_plumber:
            candidate = PlumberSession(path, opts.password)
            if candidate.open():
                session = candidate
            elif opts.table_strategy == "pdfplumber":
                warnings.append(
                    WarningItem(
                        "OPTIONAL_DEP_MISSING",
                        "pdfplumber 无法打开该 PDF，表格已回退 PyMuPDF 结果",
                    )
                )
                opts.table_strategy = "auto"

        data_dir = Path(opts.out_dir or ".").resolve()
        images_dir = data_dir / "images"
        pages: List[PageResult] = []
        mismatched_pages: List[int] = []
        cross_checked = 0

        try:
            for raw in raw_pages:
                index = int(raw["index"])
                plumber_text: Optional[str] = None
                plumber_tables: List[Dict[str, Any]] = []
                if session is not None and (
                    opts.table_strategy == "pdfplumber" or index in crosscheck_indexes
                ):
                    plumber_text, plumber_tables = session.page_data(index)

                if opts.table_strategy == "off":
                    tables = []
                    table_mismatches = []
                elif opts.table_strategy == "mupdf":
                    tables = list(raw.get("tables", []))
                    table_mismatches: List[str] = []
                elif opts.table_strategy == "pdfplumber":
                    tables = list(plumber_tables)
                    table_mismatches = []
                else:
                    tables, table_mismatches = quality.merge_tables(
                        raw["rotation"], raw.get("tables", []), plumber_tables
                    )

                chosen_text, text_engine = quality.choose_text(
                    raw.get("text"), plumber_text
                )
                page_quality = quality.evaluate_page(raw, chosen_text, text_engine)

                if opts.crosscheck and index in crosscheck_indexes:
                    checked = quality.crosscheck(raw.get("text"), plumber_text)
                elif opts.crosscheck:
                    checked = {
                        "status": "skipped",
                        "char_ratio": None,
                        "jaccard": None,
                        "pdfplumber_char_count": None,
                    }
                else:
                    checked = {
                        "status": "skipped",
                        "char_ratio": None,
                        "jaccard": None,
                        "pdfplumber_char_count": None,
                    }
                page_quality["crosscheck"] = checked
                if checked["status"] in ("match", "mismatch"):
                    cross_checked += 1
                if checked["status"] == "mismatch":
                    mismatched_pages.append(index)
                    warnings.append(
                        WarningItem(
                            "TEXT_MISMATCH",
                            "第 %d 页 PyMuPDF 与 pdfplumber 文本差异较大："
                            "char_ratio=%.3f jaccard=%.3f"
                            % (index + 1, checked["char_ratio"], checked["jaccard"]),
                            index,
                        )
                    )

                for table_id in table_mismatches:
                    warnings.append(
                        WarningItem(
                            "TABLE_MISMATCH",
                            "第 %d 页表格 %s 与 pdfplumber 结果不一致，采用 PyMuPDF 结果"
                            % (index + 1, table_id),
                            index,
                        )
                    )

                if page_quality["cid_glyphs"]:
                    warnings.append(
                        WarningItem(
                            "CID_GLYPHS",
                            "第 %d 页存在 %d 个 (cid:) 字形，文本可能不完整"
                            % (index + 1, page_quality["cid_glyphs"]),
                            index,
                        )
                    )
                if page_quality["replacement_chars"]:
                    warnings.append(
                        WarningItem(
                            "REPLACEMENT_CHARS",
                            "第 %d 页存在 %d 个替换字符（U+FFFD），可能有编码问题"
                            % (index + 1, page_quality["replacement_chars"]),
                            index,
                        )
                    )
                if not page_quality["text_layer"]:
                    if page_quality["image_coverage"] >= 0.8:
                        detail = "图片覆盖 %.0f%%，疑似扫描件" % (
                            page_quality["image_coverage"] * 100
                        )
                    else:
                        detail = "可提取字符少于 10 个"
                    warnings.append(
                        WarningItem(
                            "NO_TEXT_LAYER",
                            "第 %d 页无文本层（%s）；未执行 OCR"
                            % (index + 1, detail),
                            index,
                        )
                    )

                ordered_blocks, layout_info = layout.order_blocks(
                    raw.get("blocks", []),
                    raw.get("words", []),
                    raw.get("layout_rect") or raw["rect"],
                )
                layout.mark_furniture(ordered_blocks, furniture.get(index, []))

                images = (
                    [] if opts.images == "none" else _image_rects(raw)
                )
                if opts.images == "extract" and images:
                    _extract_images(doc, raw, images_dir, warnings)

                headers_footers = [
                    {
                        "zone": record["zone"],
                        "text": record["text"],
                        "bbox": record["bbox"],
                        "is_page_number": record["is_page_number"],
                    }
                    for record in furniture.get(index, [])
                ]

                pages.append(
                    PageResult(
                        index=index,
                        number=index + 1,
                        width=float(raw["rect"].width),
                        height=float(raw["rect"].height),
                        rotation=int(raw["rotation"]),
                        coordinate_space="mupdf_unrotated_top_left",
                        text_layer=bool(page_quality["text_layer"]),
                        char_count=int(page_quality["char_count"]),
                        word_count=int(page_quality["word_count"]),
                        layout=layout_info,
                        quality=page_quality,
                        blocks=ordered_blocks,
                        text=chosen_text,
                        tables=tables,
                        links=list(raw.get("links", [])),
                        images=images,
                        headers_footers=headers_footers,
                    )
                )
        finally:
            if session is not None:
                session.close()

        if pages and all(not page.text_layer for page in pages):
            warnings.append(
                WarningItem(
                    "SCANNED_PDF",
                    "所选页面均无文本层，可能是扫描版 PDF；本工具不执行 OCR",
                )
            )

        all_links: List[Dict[str, Any]] = []
        for page in pages:
            for link in page.links:
                entry = dict(link)
                entry["page_index"] = page.index
                all_links.append(entry)

        document = dict(collect_document_meta(doc, path, opts.password))
        document["page_count"] = page_count
        document["selected_pages"] = [page.number for page in pages]
        document["links"] = all_links
        if document.get("access") == "owner":
            warnings.append(
                WarningItem(
                    "PASSWORD_OWNER",
                    "使用了 owner 密码打开 PDF，权限比 user 密码更宽",
                )
            )

        source = {
            "path": path.as_posix(),
            "file_name": path.name,
            "size_bytes": size_bytes,
            "sha256": _sha256(path),
        }

        duration_ms = int((time.time() - started) * 1000)
        generated_at = (
            _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        extraction = {
            "generated_at": generated_at,
            "duration_ms": duration_ms,
            "options": opts.public(),
            "counts": {
                "pages": len(pages),
                "chars": sum(page.char_count for page in pages),
                "tables": sum(len(page.tables) for page in pages),
                "images": sum(len(page.images) for page in pages),
                "warnings": len(warnings),
                "headers_footers": furniture_lines,
            },
            "crosscheck": {
                "pages_checked": cross_checked,
                "sampled": bool(sampled and opts.crosscheck),
                "mismatched_pages": sorted(set(mismatched_pages)),
            },
        }
        return DocumentResult(
            source=source,
            document=document,
            pages=pages,
            warnings=warnings,
            extraction=extraction,
        )
    finally:
        doc.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract.py",
        description="Read a PDF into structured JSON plus reading-order Markdown (no OCR).",
    )
    parser.add_argument("input", help="input PDF path")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="output directory (default: ./pdfdata_out/<file-stem>/)",
    )
    parser.add_argument(
        "--format",
        choices=("both", "json", "md", "text"),
        default="both",
        help="output format (default: both)",
    )
    parser.add_argument(
        "--pages",
        default=None,
        help="1-based page selection, e.g. 1-3,5 (default: all pages)",
    )
    parser.add_argument("--password", default=None, help="PDF password, if encrypted")
    parser.add_argument(
        "--table-strategy",
        choices=("auto", "mupdf", "pdfplumber", "off"),
        default="auto",
        help="table extraction strategy (default: auto)",
    )
    parser.add_argument(
        "--images",
        choices=("none", "meta", "extract"),
        default="meta",
        help="image handling (default: meta; extract writes images/)",
    )
    parser.add_argument(
        "--keep-headers",
        action="store_true",
        help="keep detected headers/footers in Markdown body",
    )
    parser.add_argument(
        "--char-coords",
        action="store_true",
        help="include per-character bboxes (larger JSON)",
    )
    parser.add_argument(
        "--no-crosscheck",
        action="store_true",
        help="skip pdfplumber text cross-check (faster)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the selected format to stdout instead of writing files",
    )
    return parser


def _print_summary(result: DocumentResult, written: Sequence[Path]) -> None:
    counts = result.extraction.get("counts", {})
    print(
        "[pdf-data] pages=%s chars=%s tables=%s images=%s warnings=%s"
        % (
            counts.get("pages"),
            counts.get("chars"),
            counts.get("tables"),
            counts.get("images"),
            counts.get("warnings"),
        ),
        file=sys.stderr,
    )
    for path in written:
        print("  -> %s" % path, file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _reconfigure_utf8()
    args = _build_parser().parse_args(argv)

    path = Path(args.input)
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else Path.cwd() / "pdfdata_out" / path.stem
    )
    options = Options(
        out_dir=str(out_dir),
        fmt=args.format,
        pages_spec=args.pages,
        password=args.password,
        table_strategy=args.table_strategy,
        images=args.images,
        keep_headers=args.keep_headers,
        char_coords=args.char_coords,
        crosscheck=not args.no_crosscheck,
        stdout=args.stdout,
    )

    try:
        result = extract_document(path, options)
    except EncryptedPdfError as exc:
        print("错误：%s" % exc.message, file=sys.stderr)
        return 3
    except PdfDataError as exc:
        print("错误：%s" % exc.message, file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected failures
        if os.environ.get("PDFDATA_DEBUG"):
            traceback.print_exc()
        else:
            print("错误：处理失败：%s" % exc, file=sys.stderr)
        return 1

    json_text = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    markdown_text = render.to_markdown(result, options.keep_headers)
    plain_text = render.to_plain_text(result, options.keep_headers)

    written: List[Path] = []
    try:
        if options.stdout:
            if options.fmt in ("json", "both"):
                sys.stdout.write(json_text + "\n")
            elif options.fmt == "md":
                sys.stdout.write(markdown_text)
            else:
                sys.stdout.write(plain_text)
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            if options.fmt in ("json", "both"):
                target = out_dir / "document.json"
                _atomic_write_text(target, json_text + "\n")
                written.append(target)
            if options.fmt in ("md", "both"):
                target = out_dir / "document.md"
                _atomic_write_text(target, markdown_text)
                written.append(target)
            if options.fmt == "text":
                target = out_dir / "document.txt"
                _atomic_write_text(target, plain_text)
                written.append(target)
    except OSError as exc:
        print("错误：写出结果失败：%s" % exc, file=sys.stderr)
        return 2

    if options.images == "extract":
        images_dir = out_dir / "images"
        if images_dir.is_dir():
            print("  -> %s" % images_dir, file=sys.stderr)

    _print_summary(result, written)

    all_without_text = bool(result.pages) and all(
        not page.text_layer for page in result.pages
    )
    return 4 if all_without_text else 0


if __name__ == "__main__":
    sys.exit(main())
