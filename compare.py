#!/usr/bin/env python3
"""Render photos through a matrix of conversion options into an HTML
comparison gallery.

    python3 compare.py photos/kenneth/IMG_3783.jpeg           # one photo
    python3 compare.py photos/kenneth/*.jpeg                  # several
    python3 compare.py --dir photos/kenneth                   # whole folder
    open build/compare/compare.html
"""

import argparse
import html
import pathlib
import sys

from PIL import Image

try:                            # optional: modern-format decoders
    import pillow_avif  # noqa: F401
    import pillow_jxl   # noqa: F401
except ImportError:
    pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import convert
import preview

EXTS = (".jpg", ".jpeg", ".png", ".heic", ".webp", ".avif", ".jxl")

VARIANTS = [
    ("dizzy s=0.5 (default)", {}),
    ("hybrid s=0.85", {"dither": "hybrid", "strength": 0.85}),
    ("hybrid s=1.2", {"dither": "hybrid", "strength": 1.2}),
    ("fs s=0.85", {"dither": "fs"}),
    ("fs s=0.5", {"dither": "fs", "strength": 0.5}),
    ("fs s=1.2", {"dither": "fs", "strength": 1.2}),
    ("atkinson s=0.5", {"dither": "atkinson", "strength": 0.5}),
    ("atkinson s=0.85", {"dither": "atkinson"}),
    ("atkinson s=1.2", {"dither": "atkinson", "strength": 1.2}),
    ("dizzy s=0.85", {"dither": "dizzy", "strength": 0.85}),
    ("dizzy s=1.2", {"dither": "dizzy", "strength": 1.2}),
    ("riemersma s=0.85", {"dither": "riemersma"}),
    ("riemersma s=1.2", {"dither": "riemersma", "strength": 1.2}),
    ("bayer4 s=0.85", {"dither": "bayer4"}),
    ("bayer4 s=1.2", {"dither": "bayer4", "strength": 1.2}),
    ("bayer8 s=0.85", {"dither": "bayer8"}),
    ("bayer8 s=1.2", {"dither": "bayer8", "strength": 1.2}),
    ("sat 0.9", {"sat": 0.9}),
    ("sat 1.3", {"sat": 1.3}),
    ("gamma 0.85 (brighter mids)", {"gamma": 0.85}),
    ("gamma 1.2 (darker mids)", {"gamma": 1.2}),
]


def flags(over):
    return " ".join(f"--{k} {v}" for k, v in over.items()) or "(defaults)"


def render_photo(photo_path, out, section):
    photo = Image.open(photo_path)
    cards = []
    orig = photo.copy()
    orig.thumbnail((640, 480))
    ofn = f"{section}_orig.png"
    orig.save(out / ofn)
    cards.append(("original", "", ofn))
    for n, (label, over) in enumerate(VARIANTS):
        img = convert.convert_image(photo, convert.Settings(**over))
        fn = f"{section}_v{n:02d}.png"
        preview.render(img).resize((640, 400), Image.NEAREST).save(out / fn)
        cards.append((label, flags(over), fn))
        print(f"  {label:28s} -> {fn}")
    tiles = "\n".join(
        f'<figure><img src="{fn}" loading="lazy">'
        f"<figcaption>{html.escape(label)}"
        f'{f"<br><code>{html.escape(fl)}</code>" if fl else ""}'
        f"</figcaption></figure>"
        for label, fl, fn in cards)
    return (f'<h2 id="{section}">{html.escape(photo_path.name)}</h2>\n'
            f'<div class="grid">\n{tiles}\n</div>')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photos", nargs="*", type=pathlib.Path)
    ap.add_argument("--dir", type=pathlib.Path)
    ap.add_argument("--only", help="comma-separated label prefixes, e.g. atkinson,dizzy")
    args = ap.parse_args()
    if args.only:
        keys = [k.strip() for k in args.only.split(",")]
        global VARIANTS
        VARIANTS = [v for v in VARIANTS if any(v[0].startswith(k) for k in keys)]
    photos = list(args.photos)
    if args.dir:
        photos += sorted(p for p in args.dir.iterdir()
                         if p.suffix.lower() in EXTS and not p.name.startswith("."))
    if not photos:
        raise SystemExit("give photo paths or --dir")

    out = pathlib.Path(__file__).resolve().parent / "build" / "compare"
    out.mkdir(parents=True, exist_ok=True)

    sections, nav = [], []
    for i, p in enumerate(photos):
        print(f"[{i + 1}/{len(photos)}] {p.name}")
        sec = f"p{i:02d}"
        sections.append(render_photo(p, out, sec))
        nav.append(f'<a href="#{sec}">{html.escape(p.name)}</a>')

    (out / "compare.html").write_text(f"""<!doctype html>
<meta charset="utf-8"><title>FLI conversion options</title>
<style>
 body {{ background:#111; color:#ddd; font:14px/1.4 system-ui; margin:2rem }}
 h1 {{ font-size:1.3rem }} h2 {{ font-size:1.1rem; margin-top:2.5rem }}
 nav {{ position:sticky; top:0; background:#111a; backdrop-filter:blur(6px);
       padding:.5rem 0; display:flex; flex-wrap:wrap; gap:.8rem }}
 nav a {{ color:#8cf; text-decoration:none }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:1rem }}
 figure {{ margin:0 }}
 img {{ width:100%; image-rendering:pixelated; border:1px solid #333 }}
 figcaption {{ padding:.3rem 0; color:#aaa }} code {{ color:#8cf }}
</style>
<h1>FLI conversion options — {len(photos)} photo(s)</h1>
<p>apply a look: <code>python3 convert.py &lt;photo&gt; &lt;flags&gt;</code> — it sticks via the sidecar; then <code>python3 mkdisk.py --dir …</code></p>
<nav>{' '.join(nav)}</nav>
{chr(10).join(sections)}""")
    print(f"\nopen {out / 'compare.html'}")


if __name__ == "__main__":
    main()
