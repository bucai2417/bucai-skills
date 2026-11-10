#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate assets/icon-512.png (512x512) for the pdf-data skill."""

from __future__ import annotations

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "icon-512.png"

BLUE = (0.145, 0.388, 0.921)
WHITE = (1.0, 1.0, 1.0)
INK = (0.12, 0.16, 0.24)


def main() -> int:
    fitz.no_recommend_layout()
    doc = fitz.open()
    page = doc.new_page(width=512, height=512)

    page.draw_rect(page.rect, color=None, fill=BLUE)

    card = fitz.Rect(96, 120, 416, 392)
    page.draw_rect(card, color=None, fill=WHITE)

    fold = fitz.Rect(352, 120, 416, 184)
    page.draw_polyline(
        [(352, 120), (352, 184), (416, 184)], color=None, fill=(0.78, 0.85, 1.0)
    )
    page.draw_polyline([(352, 120), (416, 184)], color=BLUE, width=6)

    page.insert_text(
        (124, 258),
        "PDF",
        fontname="hebo",
        fontsize=74,
        color=BLUE,
    )
    for index, width in enumerate((200, 180, 140)):
        y = 292 + index * 24
        page.draw_line((124, y), (124 + width, y), color=INK, width=8)

    pixmap = page.get_pixmap(alpha=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(OUTPUT))
    doc.close()
    print("wrote %s (%dx%d)" % (OUTPUT, pixmap.width, pixmap.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
