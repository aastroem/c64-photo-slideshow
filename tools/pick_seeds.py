#!/usr/bin/env python3
"""Score candidate picsum seeds for FLI-friendliness and build a contact sheet.

Dev tool, not part of the build. It scores picsum seeds; the shipped deck in
samples/ was curated the same way (score, then a human picks from the sheet),
so this stays useful for scouting new candidates.

    python3 tools/pick_seeds.py            # scan, score, write the sheet
    open build/seedscan/index.html

FLI rewards color freedom and detail; it punishes big flat gradients (a sky
bands, a wall shows the dither). So: reward chroma spread and edge density,
penalize the fraction of the frame sitting in near-uniform blocks.
"""

import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import c64color
import convert
import preview

CANDIDATES = [
    "parrot", "market", "spices", "graffiti", "stainedglass", "tulips",
    "carnival", "harbor", "lantern", "mosaic", "autumn", "coral",
    "balloons", "bazaar", "chameleon", "macaw", "peacock", "quilt",
    "murals", "neon", "arcade", "kimono", "festival", "orchard",
    "pumpkins", "chilis", "candy", "butterfly", "koi", "reef",
    "vineyard", "wildflowers", "canyon", "aurora", "bookshelf", "bicycles",
    "rooftops", "venice", "tuktuk", "rickshaw", "surfboards", "kites",
    "produce", "flamingo", "toucan", "hotairballoon", "sari", "temple",
    "tiles", "mural", "junkshop", "flowershop", "fruitstand", "yarn",
    "carousel", "pier", "boats", "cathedral", "fireworks", "garden",
]
SCAN = pathlib.Path(__file__).resolve().parents[1] / "build" / "seedscan"


def fetch(seed):
    dest = SCAN / f"{seed}.jpg"
    if not dest.exists():
        subprocess.run(
            ["curl", "-fsSL", "-o", str(dest),
             f"https://picsum.photos/seed/{seed}/1200/900.jpg"], check=True)
    return dest


def score(path):
    """(score, chroma, edge, flat) for the image the converter actually sees."""
    vis = convert.prepare(Image.open(path), convert.Settings())   # 144x200 RGB
    lab = c64color.srgb_to_oklab(np.asarray(vis, dtype=np.uint8))
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]

    chroma = float(np.hypot(a, b).mean())
    edge = float(np.abs(np.diff(L, axis=0)).mean()
                 + np.abs(np.diff(L, axis=1)).mean())

    # flat = fraction of 8x8 blocks that are near-uniform in both L and chroma
    h, w = L.shape
    bh, bw = h // 8, w // 8
    Lb = L[:bh * 8, :bw * 8].reshape(bh, 8, bw, 8).std(axis=(1, 3))
    C = np.hypot(a, b)[:bh * 8, :bw * 8].reshape(bh, 8, bw, 8).std(axis=(1, 3))
    flat = float(((Lb < 0.02) & (C < 0.01)).mean())

    return 10 * chroma + 20 * edge - 1.5 * flat, chroma, edge, flat


def main():
    SCAN.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in CANDIDATES:
        src = fetch(seed)
        s, chroma, edge, flat = score(src)
        img = convert.convert_image(Image.open(src), convert.Settings())
        pv = SCAN / f"{seed}_fli.png"
        preview.render(img).resize((576, 400), Image.NEAREST).save(pv)
        rows.append((s, seed, chroma, edge, flat, pv.name))
        print(f"{seed:16s} score {s:6.3f}  chroma {chroma:.3f}  "
              f"edge {edge:.3f}  flat {flat:.2f}")

    rows.sort(reverse=True)
    cards = "\n".join(
        f'<figure><img src="{pv}" width="288">'
        f'<figcaption>{i}. <b>{seed}</b> — score {s:.2f}, chroma {c:.3f}, '
        f'edge {e:.3f}, flat {f:.0%}</figcaption></figure>'
        for i, (s, seed, c, e, f, pv) in enumerate(rows, 1))
    (SCAN / "index.html").write_text(
        "<style>body{background:#222;color:#eee;font:14px sans-serif}"
        "figure{display:inline-block;margin:8px}</style>\n" + cards)
    print(f"\nwrote {SCAN / 'index.html'} — pick ten, keeping subject variety")


if __name__ == "__main__":
    main()
