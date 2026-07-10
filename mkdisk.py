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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=pathlib.Path, default=HERE / "photos")
    ap.add_argument("--force", action="store_true", help="reconvert all photos")
    args = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    sh(sys.executable, "gen_tables.py")

    photos = ordered_photos(args.dir)
    if not 2 <= len(photos) <= MAX_PICS:
        raise SystemExit(f"need 2-{MAX_PICS} photos in {args.dir}, found {len(photos)}")
    print("slide order:")
    for i, p in enumerate(photos, 1):
        print(f"  {i:2d}. {p.name}  ({shot_time(p):%Y-%m-%d %H:%M})")

    packed = []
    for i, photo in enumerate(photos, 1):
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
