#!/bin/sh
# Everything in one go: setup (if needed) -> disk image -> emulator.
#   ./go.sh              the curated Norway deck in samples/
#   ./go.sh my-photos/   your own directory of 2-18 images
set -e
cd "$(dirname "$0")"

[ -x src/loader/loader/tools/dali/dali ] || ./setup.sh

DIR=${1:-samples}

# --fill: pack as many slides as the disk holds rather than refusing to build.
# Slide sizes track how well each photo crunches, so a deck that fit yesterday
# can overflow after a settings change; go.sh should always produce a disk and
# say what it dropped. Run mkdisk.py without --fill to get the hard error back.
echo "== building build/slideshow.d64"
python3 mkdisk.py --dir "$DIR" --fill

echo "== starting VICE (x64sc). Space or joystick-2 fire skips slides."
exec ./run_emulator.sh
