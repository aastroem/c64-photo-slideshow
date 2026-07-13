#!/usr/bin/env python3
"""Download 10 openly licensed sample photos (picsum.photos, Unsplash license)
into photos/ as stand-ins until the real vacation photos arrive. Idempotent.
Fixed seeds make the set reproducible; sources recorded in photos/SOURCES.txt.
"""

import pathlib
import subprocess

SEEDS = ["festival", "quilt", "carousel", "lantern", "reef",
         "pumpkins", "rickshaw", "orchard", "produce", "flamingo"]

photos = pathlib.Path(__file__).resolve().parent / "photos"
photos.mkdir(exist_ok=True)

lines = []
for i, seed in enumerate(SEEDS, 1):
    url = f"https://picsum.photos/seed/{seed}/1200/900.jpg"
    dest = photos / f"sample{i:02d}.jpg"
    lines.append(f"{dest.name}: {url} (picsum.photos, Unsplash-licensed photos)")
    if dest.exists():
        print(f"kept   {dest.name}")
        continue
    subprocess.run(["curl", "-fsSL", "-o", str(dest), url], check=True)
    print(f"fetched {dest.name} <- {url}")

(photos / "SOURCES.txt").write_text("\n".join(lines) + "\n")
