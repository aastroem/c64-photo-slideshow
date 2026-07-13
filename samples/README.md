# Sample photos

The deck that ships with the project. Drop your curated picks straight in
here — these files are **committed**, unlike `photos/`, which is gitignored
and stays local.

    samples/
      01.jpg              <- optional: a leading "01." pins the first slide
      harbour.jpg
      harbour.jpg.c64.json    <- per-photo settings, written by the converter

## Rules

- **2–18 slides.** Two portrait photos are paired into one side-by-side
  slide, so you can have more *photos* than slides. `mkdisk.py` sums the
  actual crunched blocks and refuses to write an over-capacity disk, so the
  real ceiling depends on how well your photos compress.
- **Licensing matters here.** These images land in git history, so use your
  own photos or openly licensed ones. Record where they came from in
  `SOURCES.txt` next to them.
- **Order** is `01.*` first (if present), then EXIF capture time.
- Formats: JPG/PNG/WebP, plus AVIF/JXL/HEIC if `setup.sh` installed the
  optional decoders.

## Curating

Convert one photo and look at the generated `_preview.png` before committing
to a pick — it is exactly what the C64 will show:

    python3 convert.py samples/harbour.jpg

Pin per-photo settings by passing flags; they persist to the sidecar and are
reused by every later build:

    python3 convert.py samples/harbour.jpg --mode afli --dither fs --sat 1.2

Photos that survive the C64 palette well tend to have strong local color and
detail; big flat gradients (empty sky, haze) band badly. See `tools/pick_seeds.py`
for the scoring heuristic used to pick the previous picsum-based set.

Build and run the whole deck:

    ./go.sh samples/
