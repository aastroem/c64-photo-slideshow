#!/bin/sh
# One-time setup: check prerequisites and build the ZX0 cruncher.
# Works on macOS and Linux (on Windows, run inside WSL) -- see README.
set -e
cd "$(dirname "$0")"

# pick install hints for this platform
if command -v brew >/dev/null; then
    ACME_HINT="brew install acme"; VICE_HINT="brew install vice"
    CC_HINT="xcode-select --install"; PY_HINT="brew install python"
elif command -v apt-get >/dev/null; then
    ACME_HINT="sudo apt install acme"; VICE_HINT="sudo apt install vice  (see README: VICE on Debian/Ubuntu needs C64 ROMs added)"
    CC_HINT="sudo apt install build-essential"; PY_HINT="sudo apt install python3 python3-pip"
elif command -v pacman >/dev/null; then
    ACME_HINT="pacman -S acme  (or AUR)"; VICE_HINT="pacman -S vice"
    CC_HINT="pacman -S base-devel"; PY_HINT="pacman -S python python-pip"
elif command -v dnf >/dev/null; then
    ACME_HINT="see README (build ACME from source)"; VICE_HINT="sudo dnf install vice"
    CC_HINT="sudo dnf groupinstall 'Development Tools'"; PY_HINT="sudo dnf install python3 python3-pip"
else
    ACME_HINT="install the ACME cross-assembler"; VICE_HINT="install VICE (x64sc, c1541)"
    CC_HINT="install a C compiler and make"; PY_HINT="install Python 3"
fi

echo "== checking prerequisites"
for tool in acme x64sc c1541 python3 cc make; do
    if ! command -v $tool >/dev/null; then
        case $tool in
            acme)        echo "missing: acme     -> $ACME_HINT" ;;
            x64sc|c1541) echo "missing: $tool    -> $VICE_HINT" ;;
            cc|make)     echo "missing: $tool    -> $CC_HINT" ;;
            python3)     echo "missing: python3  -> $PY_HINT" ;;
        esac
        MISSING=1
    else
        echo "ok: $tool"
    fi
done
[ -n "$MISSING" ] && { echo; echo "install the missing tools above, then re-run ./setup.sh"; exit 1; }

echo "== python packages"
if python3 -c "import PIL, numpy, pytest" 2>/dev/null; then
    echo "ok: Pillow, numpy, pytest already available"
else
    # PEP 668 distros refuse plain pip installs; fall back accordingly
    python3 -m pip install --quiet Pillow numpy pytest 2>/dev/null \
        || python3 -m pip install --quiet --user --break-system-packages Pillow numpy pytest \
        || { echo "pip failed -- install Pillow and numpy with your package"
             echo "manager (e.g. sudo apt install python3-pil python3-numpy python3-pytest)"
             exit 1; }
    echo "ok: Pillow, numpy, pytest"
fi

# optional decoders for webp/avif/jxl photos (best effort)
python3 -m pip install --quiet pillow-avif-plugin pillow-jxl-plugin 2>/dev/null \
    || python3 -m pip install --quiet --user --break-system-packages pillow-avif-plugin pillow-jxl-plugin 2>/dev/null \
    || echo "note: avif/jxl photo support skipped (jpg/png/webp still fine)"

echo "== building dali (ZX0 cruncher, vendored with Krill's loader)"
DALI=src/loader/loader/tools/dali
if [ ! -x $DALI/dali ]; then
    # upstream Makefile needs GNU objcopy; rename salvador's main at compile
    # time instead so plain clang/gcc works everywhere
    make -C $DALI/salvador CFLAGS='-O3 -fomit-frame-pointer -Isrc/libdivsufsort/include -Isrc -fPIC -Dmain=salvador_main' >/dev/null 2>&1 || true
    ar rcs $DALI/salvador.a $DALI/salvador/obj/src/*.o $DALI/salvador/obj/src/libdivsufsort/lib/*.o
    cc -Os -o $DALI/dali $DALI/dali.c $DALI/salvador.a
fi
echo "ok: dali"

echo
echo "setup complete. next:  ./go.sh              (sample photos)"
echo "                       ./go.sh my-photos/   (your own, 2-18 images)"
