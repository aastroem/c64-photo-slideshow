#!/bin/sh
# One-time setup: check prerequisites and build the ZX0 cruncher.
# Prerequisites (macOS): Homebrew, Xcode command line tools (for cc/make).
set -e
cd "$(dirname "$0")"

echo "== checking prerequisites"
for tool in acme x64sc c1541 python3 cc make; do
    if ! command -v $tool >/dev/null; then
        case $tool in
            acme)        echo "missing: acme        -> brew install acme"; MISSING=1 ;;
            x64sc|c1541) echo "missing: $tool       -> brew install vice"; MISSING=1 ;;
            cc|make)     echo "missing: $tool       -> xcode-select --install"; MISSING=1 ;;
            python3)     echo "missing: python3     -> brew install python"; MISSING=1 ;;
        esac
    else
        echo "ok: $tool"
    fi
done
[ -n "$MISSING" ] && { echo "install the missing tools above, then re-run ./setup.sh"; exit 1; }

echo "== python packages"
python3 -m pip install --quiet Pillow numpy pytest
echo "ok: Pillow, numpy, pytest"

echo "== building dali (ZX0 cruncher, vendored with Krill's loader)"
DALI=src/loader/loader/tools/dali
if [ ! -x $DALI/dali ]; then
    # upstream Makefile needs GNU objcopy; rename salvador's main at compile
    # time instead so plain clang works on macOS
    make -C $DALI/salvador CFLAGS='-O3 -fomit-frame-pointer -Isrc/libdivsufsort/include -Isrc -fPIC -Dmain=salvador_main' >/dev/null 2>&1 || true
    ar rcs $DALI/salvador.a $DALI/salvador/obj/src/*.o $DALI/salvador/obj/src/libdivsufsort/lib/*.o
    cc -Os -o $DALI/dali $DALI/dali.c $DALI/salvador.a
fi
echo "ok: dali"

echo
echo "setup complete. next:  ./go.sh              (sample photos)"
echo "                       ./go.sh my-photos/   (your own, 2-11 images)"
