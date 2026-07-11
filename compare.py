#!/usr/bin/env python3
"""Render one photo through a matrix of conversion options into an HTML
comparison gallery.

    python3 compare.py photos/kenneth/IMG_3783.jpeg
    open build/compare/compare.html
"""

import argparse
import html
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import convert
import preview

VARIANTS = [
    # (label, settings overrides)
    ("hybrid s=0.85 (default)", {}),
    ("hybrid s=0.5", {"strength": 0.5}),
    ("hybrid s=1.2", {"strength": 1.2}),
    ("fs s=0.85", {"dither": "fs"}),
    ("fs s=0.5", {"dither": "fs", "strength": 0.5}),
    ("fs s=1.2", {"dither": "fs", "strength": 1.2}),
    ("bayer4 s=0.85", {"dither": "bayer4"}),
    ("bayer4 s=1.2", {"dither": "bayer4", "strength": 1.2}),
    ("bayer8 s=0.85", {"dither": "bayer8"}),
    ("bayer8 s=1.2", {"dither": "bayer8", "strength": 1.2}),
    ("sat 0.9", {"sat": 0.9}),
    ("sat 1.3", {"sat": 1.3}),
    ("gamma 0.85 (brighter mids)", {"gamma": 0.85}),
    ("gamma 1.2 (darker mids)", {"gamma": 1.2}),
    ("crop up", {"crop": "0,-0.6"}),
    ("crop down", {"crop": "0,0.6"}),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=pathlib.Path)
    args = ap.parse_args()

    out = pathlib.Path(__file__).resolve().parent / "build" / "compare"
    out.mkdir(parents=True, exist_ok=True)
    photo = Image.open(args.photo)

    cards = []
    orig = photo.copy()
    orig.thumbnail((640, 480))
    orig.save(out / "original.png")
    cards.append(("original", "original.png"))

    for n, (label, over) in enumerate(VARIANTS):
        s = convert.Settings(**over)
        img = convert.convert_image(photo, s)
        fn = f"v{n:02d}.png"
        preview.render(img).resize((640, 400), Image.NEAREST).save(out / fn)
        cards.append((label, fn))
        print(f"{label:32s} -> {fn}")

    tiles = "\n".join(
        f'<figure><img src="{fn}" loading="lazy">'
        f"<figcaption>{html.escape(label)}</figcaption></figure>"
        for label, fn in cards)
    (out / "compare.html").write_text(f"""<!doctype html>
<meta charset="utf-8"><title>{html.escape(args.photo.name)} — FLI options</title>
<style>
 body {{ background:#111; color:#ddd; font:14px/1.4 system-ui; margin:2rem }}
 h1 {{ font-size:1.2rem; font-weight:600 }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:1rem }}
 figure {{ margin:0 }}
 img {{ width:100%; image-rendering:pixelated; border:1px solid #333 }}
 figcaption {{ padding:.3rem 0; color:#aaa }}
</style>
<h1>{html.escape(args.photo.name)} — conversion options</h1>
<p>tune with: <code>python3 convert.py {html.escape(str(args.photo))} --dither … --strength … --sat … --gamma … --crop dx,dy</code></p>
<div class="grid">
{tiles}
</div>""")
    print(f"\nopen {out / 'compare.html'}")


if __name__ == "__main__":
    main()
