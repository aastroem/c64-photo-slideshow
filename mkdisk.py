#!/usr/bin/env python3
"""One-shot build: photos -> build/slideshow.d64.

  python3 mkdisk.py [--dir photos/kenneth] [--force]

Takes 2-11 photos from the directory (default photos/). Slide order: a file
named 01.* comes first, the rest sort by EXIF capture time (file mtime when
absent). Pics are ZX0-crunched (Krill loadcompd). Boot: LOAD"*",8,1 + RUN.
Verify:  ./run_emulator.sh
"""

import argparse
import datetime
import pathlib
import subprocess
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
BUILD = HERE / "build"
DALI = HERE / "src/loader/loader/tools/dali/dali"
MAX_BLOCKS = 664
MAX_PICS = 11
EXTS = (".jpg", ".jpeg", ".png", ".heic")


def sh(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=HERE)


def blocks(path):
    return (path.stat().st_size - 2 + 253) // 254


def shot_time(photo):
    try:
        ex = Image.open(photo).getexif()
        dt = ex.get(36867) or ex.get(306)
        if dt:
            return datetime.datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.datetime.fromtimestamp(photo.stat().st_mtime)


def ordered_photos(d):
    photos = [p for p in d.iterdir()
              if p.suffix.lower() in EXTS and not p.name.startswith(".")]
    pinned = [p for p in photos if p.stem == "01"]
    rest = sorted((p for p in photos if p.stem != "01"), key=shot_time)
    return pinned + rest


def is_portrait(p):
    from PIL import ImageOps
    im = ImageOps.exif_transpose(Image.open(p))
    return im.width / im.height < 1.1


def build_slides(photos):
    """Pair portraits (in shot order) into side-by-side slides.

    Landscapes and a pinned 01.* stay solo; an odd portrait out remains a
    single padded slide. A pair takes its position from its first photo.
    """
    portraits = [p for p in photos if p.stem != "01" and is_portrait(p)]
    firsts = {portraits[i]: portraits[i + 1]
              for i in range(0, len(portraits) - 1, 2)}
    seconds = set(firsts.values())
    slides = []
    for p in photos:
        if p in seconds:
            continue
        slides.append((p, firsts[p]) if p in firsts else (p,))
    return slides


def composite_pair(a, b, out):
    """Two portraits -> one landscape slide, sized to the FLI display.

    The visible FLI frame is 144 multicolor pixels (each 2 hires px wide) by
    200 lines. Each photo gets exactly 71 mc px, split by a 2 mc px black
    divider (71+2+71 = 144), so the converter crops nothing afterwards and
    the divider lands on whole C64 pixels.
    """
    if out.exists() and out.stat().st_mtime > max(a.stat().st_mtime,
                                                  b.stat().st_mtime):
        return
    from PIL import ImageOps
    H_SRC = 2000                             # working height (square pixels)
    scale = H_SRC // 200                     # source px per C64 line
    half_w = 71 * 2 * scale // 2             # 71 mc px in square pixels
    gap_w = 2 * 2 * scale // 2               # 2 mc px divider
    halves = []
    for p in (a, b):
        im = ImageOps.exif_transpose(Image.open(p).convert("RGB"))
        cw = min(im.width, round(im.height * half_w / H_SRC))
        ch = min(im.height, round(im.width * H_SRC / half_w))
        x0, y0 = (im.width - cw) // 2, (im.height - ch) // 2
        halves.append(im.crop((x0, y0, x0 + cw, y0 + ch))
                        .resize((half_w, H_SRC), Image.LANCZOS))
    canvas = Image.new("RGB", (half_w * 2 + gap_w, H_SRC), (0, 0, 0))
    canvas.paste(halves[0], (0, 0))
    canvas.paste(halves[1], (half_w + gap_w, 0))
    canvas.save(out, quality=95)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=pathlib.Path, default=HERE / "photos")
    ap.add_argument("--force", action="store_true", help="reconvert all photos")
    args = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    sh(sys.executable, "gen_tables.py")

    photos = ordered_photos(args.dir)
    slides = build_slides(photos)
    if not 2 <= len(slides) <= MAX_PICS:
        raise SystemExit(f"need 2-{MAX_PICS} slides from {args.dir}, got {len(slides)}")
    print("slide order:")
    sources = []
    for i, slide in enumerate(slides, 1):
        if len(slide) == 2:
            out = BUILD / f"pair{i:02d}.jpg"
            composite_pair(slide[0], slide[1], out)
            sources.append(out)
            print(f"  {i:2d}. {slide[0].name} + {slide[1].name}  "
                  f"({shot_time(slide[0]):%Y-%m-%d %H:%M})")
        else:
            sources.append(slide[0])
            print(f"  {i:2d}. {slide[0].name}  ({shot_time(slide[0]):%Y-%m-%d %H:%M})")

    packed = []
    for i, photo in enumerate(sources, 1):
        fli = BUILD / f"pic{i:02d}.fli"
        zx0 = BUILD / f"pic{i:02d}.zx0"
        sidecar = photo.with_name(photo.name + ".c64.json")
        stale = (args.force or not fli.exists()
                 or fli.stat().st_mtime < photo.stat().st_mtime
                 or (sidecar.exists() and fli.stat().st_mtime < sidecar.stat().st_mtime))
        if stale:
            print(f"converting {photo.name} -> {fli.name}")
            sh(sys.executable, "convert.py", photo, "-o", fli)
        if stale or not zx0.exists() or zx0.stat().st_mtime < fli.stat().st_mtime:
            sh(DALI, "-o", zx0, fli)
        packed.append(zx0)

    sh("acme", "-I", "src", "-I", "build/gen", "-f", "cbm",
       "-o", BUILD / "boot.prg", "src/boot.asm")
    sh("acme", "-I", "src", "-I", "build/gen", "-f", "cbm",
       f"-DNUM_PICS={len(photos)}", "-o", BUILD / "main.prg", "src/main.asm")

    main_prg = (BUILD / "main.prg").read_bytes()
    main_end = (main_prg[0] | main_prg[1] << 8) + len(main_prg) - 2
    assert main_end < 0x4000, f"MAIN ends at ${main_end:04x}, must stay below $4000"

    d64 = BUILD / "slideshow.d64"
    d64.unlink(missing_ok=True)
    cmd = ["c1541", "-format", "slideshow,26", "d64", str(d64),
           "-write", str(BUILD / "boot.prg"), "slideshow",
           "-write", str(BUILD / "main.prg"), "main"]
    for i, z in enumerate(packed, 1):
        cmd += ["-write", str(z), f"{i:02d}"]
    subprocess.run(cmd, check=True, capture_output=True, cwd=HERE)

    used = blocks(BUILD / "boot.prg") + blocks(BUILD / "main.prg") \
        + sum(blocks(z) for z in packed)
    per_pic = "+".join(str(blocks(z)) for z in packed)
    print(f"\nbuild/slideshow.d64: {used}/{MAX_BLOCKS} blocks "
          f"(boot {blocks(BUILD / 'boot.prg')}, main {blocks(BUILD / 'main.prg')}, "
          f"pics {per_pic})")
    assert used <= MAX_BLOCKS, "disk over capacity"

    import d64tog64
    d64tog64.convert(d64, BUILD / "slideshow.g64")


if __name__ == "__main__":
    main()
