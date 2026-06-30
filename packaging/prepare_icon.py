"""Build-time: convert Icon/WiParse.ico to BMP-only ICO for PyInstaller PE embed."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'Icon' / 'WiParse.ico'
OUT = Path(__file__).resolve().parent / 'WiParse.ico'
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _icon_dib_from_bgra(raw_bgra: bytes, width: int, height: int) -> bytes:
    row_bytes = width * 4
    xor_bitmap = b''.join(
        raw_bgra[(height - 1 - y) * row_bytes:(height - y) * row_bytes]
        for y in range(height)
    )
    and_row_bytes = ((width + 31) // 32) * 4
    and_mask = b'\x00' * (and_row_bytes * height)
    bih = struct.pack(
        '<IIIHHIIIIII', 40, width, height * 2, 1, 32, 0, len(xor_bitmap), 0, 0, 0, 0,
    )
    return bih + xor_bitmap + and_mask


def _pack_ico(dibs: list[tuple[int, int, bytes]]) -> bytes:
    header = struct.pack('<HHH', 0, 1, len(dibs))
    directory = bytearray()
    blobs = bytearray()
    offset = 6 + 16 * len(dibs)
    for width, height, dib in dibs:
        w_byte = 0 if width >= 256 else width
        h_byte = 0 if height >= 256 else height
        directory.extend(struct.pack('<BBBBHHII', w_byte, h_byte, 0, 0, 1, 32, len(dib), offset))
        blobs.extend(dib)
        offset += len(dib)
    return header + bytes(directory) + bytes(blobs)


def main() -> None:
    if not SRC.is_file():
        sys.exit(f'Missing source icon: {SRC}')
    try:
        from PIL import Image
    except ImportError:
        sys.exit('Build requires Pillow: pip install Pillow')

    with Image.open(SRC) as im:
        try:
            n = im.n_frames
        except AttributeError:
            n = 1
        best = None
        best_score = -1
        for index in range(n):
            if index:
                im.seek(index)
            frame = im.convert('RGBA')
            score = frame.size[0] * frame.size[1]
            if score > best_score:
                best_score = score
                best = frame.copy()
        if best is None:
            sys.exit(f'No image frames in {SRC}')

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        w, h = best.size
        scale = min(1.0, 256 / max(w, h, 1))
        if scale < 1.0:
            best = best.resize((max(1, int(w * scale)), max(1, int(h * scale))), resample)

        dibs = []
        for size in SIZES:
            sized = best if best.size == (size, size) else best.resize((size, size), resample)
            raw = sized.convert('RGBA').tobytes('raw', 'BGRA')
            dibs.append((size, size, _icon_dib_from_bgra(raw, size, size)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(_pack_ico(dibs))
    print(f'Prepared icon: {OUT} ({OUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
