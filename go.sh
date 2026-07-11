#!/bin/sh
# Everything in one go: setup (if needed) -> photos -> disk image -> emulator.
#   ./go.sh              use openly licensed sample photos
#   ./go.sh my-photos/   use your own directory of 2-18 images
set -e
cd "$(dirname "$0")"

[ -x src/loader/loader/tools/dali/dali ] || ./setup.sh

DIR=${1:-photos}
if [ "$DIR" = "photos" ] && [ -z "$(ls photos/*.jpg 2>/dev/null)" ]; then
    echo "== fetching sample photos (picsum.photos)"
    python3 fetch_samples.py
fi

echo "== building build/slideshow.d64"
python3 mkdisk.py --dir "$DIR"

echo "== starting VICE (x64sc). Space or joystick-2 fire skips slides."
exec ./run_emulator.sh
