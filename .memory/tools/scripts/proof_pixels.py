#!/usr/bin/env python
"""Pixel-region visibility gate for proof screenshots.

Purpose: selectors/DOM assertions can pass while the posted PNG is visually useless
(for example, a tiny card at the top of a mostly blank 1920x1680 frame). This script checks
that a relevant screenshot region contains visible non-background pixels before PR posting.

Usage:
  python .memory/tools/scripts/proof_pixels.py shot.png
  python .memory/tools/scripts/proof_pixels.py shot.png --region "card:60,230,700,260:0.02"

Region format:
  label:x,y,w,h[:min_ink_ratio]

No external packages required. Supports normal Playwright PNGs (8-bit RGB/RGBA, non-interlaced).
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import struct
import sys
import zlib


PNG_SIG = b"\x89PNG\r\n\x1a\n"


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path: pathlib.Path) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIG):
        raise ValueError(f"{path}: not a PNG")

    pos = len(PNG_SIG)
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()

    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        pos += 4
        chunk_type = raw[pos : pos + 4]
        pos += 4
        chunk = raw[pos : pos + length]
        pos += length + 4  # skip crc

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None:
        raise ValueError(f"{path}: missing IHDR")
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise ValueError(
            f"{path}: unsupported PNG format bit_depth={bit_depth}, color_type={color_type}, interlace={interlace}"
        )

    channels = 3 if color_type == 2 else 4
    stride = width * channels
    data = zlib.decompress(bytes(idat))
    rows: list[list[tuple[int, int, int]]] = []
    prev = [0] * stride
    offset = 0
    bpp = channels

    for _y in range(height):
        filter_type = data[offset]
        offset += 1
        scan = list(data[offset : offset + stride])
        offset += stride
        recon = [0] * stride

        for i, value in enumerate(scan):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 0xFF
            elif filter_type == 2:
                recon[i] = (value + up) & 0xFF
            elif filter_type == 3:
                recon[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                recon[i] = (value + paeth(left, up, up_left)) & 0xFF
            else:
                raise ValueError(f"{path}: unsupported PNG filter {filter_type}")

        prev = recon
        row = []
        for x in range(width):
            base = x * channels
            row.append((recon[base], recon[base + 1], recon[base + 2]))
        rows.append(row)

    return width, height, rows


def q(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(v // 16 for v in color)


def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def parse_region(value: str, width: int, height: int, default_min: float) -> tuple[str, int, int, int, int, float]:
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"bad region '{value}', expected label:x,y,w,h[:min_ink_ratio]")
    label = parts[0]
    nums = [int(n) for n in parts[1].split(",")]
    if len(nums) != 4:
        raise ValueError(f"bad region '{value}', expected x,y,w,h")
    x, y, w, h = nums
    min_ink = float(parts[2]) if len(parts) == 3 else default_min
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return label, x, y, w, h, min_ink


def analyze_region(
    rows: list[list[tuple[int, int, int]]], x: int, y: int, w: int, h: int, threshold: int
) -> tuple[float, tuple[int, int, int, int] | None, tuple[int, int, int]]:
    pixels = [rows[yy][xx] for yy in range(y, y + h) for xx in range(x, x + w)]

    border = []
    for xx in range(x, x + w):
        border.append(rows[y][xx])
        border.append(rows[y + h - 1][xx])
    for yy in range(y, y + h):
        border.append(rows[yy][x])
        border.append(rows[yy][x + w - 1])

    bg_bucket = collections.Counter(q(p) for p in border).most_common(1)[0][0]
    bg = tuple(v * 16 + 8 for v in bg_bucket)

    ink = []
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if dist(rows[yy][xx], bg) > threshold:
                ink.append((xx, yy))

    if not ink:
        return 0.0, None, bg

    min_x = min(p[0] for p in ink)
    max_x = max(p[0] for p in ink)
    min_y = min(p[1] for p in ink)
    max_y = max(p[1] for p in ink)
    return len(ink) / len(pixels), (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1), bg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", type=pathlib.Path)
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help='label:x,y,w,h[:min_ink_ratio], repeatable. If omitted, checks the full image.',
    )
    parser.add_argument("--min-ink", type=float, default=0.01)
    parser.add_argument("--threshold", type=int, default=36)
    args = parser.parse_args()

    failed = False
    for image in args.images:
        width, height, rows = read_png(image)
        regions = args.region or [f"full:0,0,{width},{height}:{args.min_ink}"]
        print(f"{image} ({width}x{height})")
        for region in regions:
            label, x, y, w, h, min_ink = parse_region(region, width, height, args.min_ink)
            ink_ratio, bbox, bg = analyze_region(rows, x, y, w, h, args.threshold)
            status = "OK" if ink_ratio >= min_ink else "FAIL"
            bbox_text = "none" if bbox is None else f"{bbox[0]},{bbox[1]},{bbox[2]}x{bbox[3]}"
            print(
                f"  {status} {label}: region={x},{y},{w}x{h} ink={ink_ratio:.3%} "
                f"min={min_ink:.3%} bg=rgb{bg} content_bbox={bbox_text}"
            )
            if status == "FAIL":
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
