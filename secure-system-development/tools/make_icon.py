#!/usr/bin/env python3
"""Render the skill icon (512x512 PNG) without external image services.

Design: dark background, geometric shield with blue-to-cyan gradient,
and a </> mark cut into the shield. Rendered at 4x and downsampled for
clean anti-aliasing.

Usage:
    python tools/make_icon.py            # writes assets/icon-512.png
"""

from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
SS = 4                      # supersampling factor
W = SIZE * SS

BG_TOP = (8, 13, 24)
BG_BOTTOM = (17, 28, 46)
SHIELD_TOP = (59, 130, 246)     # #3B82F6
SHIELD_BOTTOM = (34, 211, 238)  # #22D3EE
MARK = (8, 13, 24)


def vertical_gradient(size, top, bottom):
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((size, size), Image.BILINEAR)


def quad(p0, p1, p2, steps=48):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def shield_points():
    cx = W / 2
    left, right = W * 0.18, W * 0.82
    top, shoulder, tip = W * 0.16, W * 0.55, W * 0.855
    r = W * 0.075

    pts = []
    # rounded top-left corner
    for i in range(25):
        a = math.pi + (math.pi / 2) * (i / 24)
        pts.append((left + r + r * math.cos(a), top + r + r * math.sin(a)))
    # rounded top-right corner
    for i in range(25):
        a = -math.pi / 2 + (math.pi / 2) * (i / 24)
        pts.append((right - r + r * math.cos(a), top + r + r * math.sin(a)))
    # right side down to shoulder
    pts.append((right, shoulder))
    # curve to tip
    pts.extend(quad((right, shoulder), (right * 0.80, tip * 0.94), (cx, tip)))
    # curve back up to left shoulder
    pts.extend(quad((cx, tip), (W - right * 0.80, tip * 0.94), (left, shoulder)))
    return pts


def draw_mark(img, box_mask):
    """Draw </> inside the shield area."""
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, W * 0.45
    stroke = int(W * 0.031)
    apex = W * 0.205        # distance from center to chevron apex
    arm = W * 0.085         # horizontal reach of each chevron arm
    height = W * 0.115      # vertical half-height

    def chevron(direction):
        tip = (cx + direction * apex, cy)
        near = cx + direction * (apex - arm)
        return [(near, cy - height), tip, (near, cy + height)]

    for direction in (-1, 1):
        pts = chevron(direction)
        d.line(pts, fill=MARK, width=stroke, joint="curve")
        for p in pts:
            d.ellipse([p[0] - stroke / 2, p[1] - stroke / 2,
                       p[0] + stroke / 2, p[1] + stroke / 2], fill=MARK)

    # slash between the chevrons
    d.line([(cx + W * 0.030, cy - height * 1.25),
            (cx - W * 0.030, cy + height * 1.25)],
           fill=MARK, width=stroke)
    for p in [(cx + W * 0.030, cy - height * 1.25), (cx - W * 0.030, cy + height * 1.25)]:
        d.ellipse([p[0] - stroke / 2, p[1] - stroke / 2,
                   p[0] + stroke / 2, p[1] + stroke / 2], fill=MARK)
    return img


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "assets")
    os.makedirs(out_dir, exist_ok=True)

    # background with a soft radial glow
    bg = vertical_gradient(W, BG_TOP, BG_BOTTOM).convert("RGBA")
    glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.12, W * 0.02, W * 0.88, W * 0.78],
               fill=(37, 99, 235, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.10))
    bg = Image.alpha_composite(bg, glow)

    # shield mask + gradient fill
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).polygon(shield_points(), fill=255)

    shield = vertical_gradient(W, SHIELD_TOP, SHIELD_BOTTOM).convert("RGBA")

    # drop shadow under the shield
    shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (0, int(W * 0.02)), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(W * 0.035))
    canvas = Image.alpha_composite(bg, shadow)

    canvas.paste(shield, (0, 0), mask)

    # inner highlight ring
    ring = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(ring).line(shield_points() + [shield_points()[0]],
                              fill=(255, 255, 255, 70), width=int(W * 0.008))
    canvas = Image.alpha_composite(canvas, ring)

    draw_mark(canvas, mask)

    icon = canvas.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    out = os.path.join(out_dir, "icon-512.png")
    icon.save(out, "PNG", optimize=True)
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
