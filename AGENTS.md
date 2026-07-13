# Repository Guidelines

## Project Structure & Module Organization

The root Python tools form the image pipeline: `convert.py` converts photos, `fli.py` defines the packed image format, `preview.py` renders previews, and `mkdisk.py` orchestrates the complete disk build. C64 assembly lives in `src/`; `boot.asm` and `main.asm` are the entry points, with effects and support routines split into focused files. Treat `src/loader/loader/` as vendored Krill loader code and avoid unrelated edits there. Tests are under `tests/`, the lightweight 6502 emulator is in `tools/`, generated files go to `build/gen/`, and final artifacts go to `build/`. See `TECHNICAL.md` before changing memory layout, raster timing, or loader integration.

## Build, Test, and Development Commands

- `./setup.sh` checks ACME, VICE, Python, compiler tools, Pillow, and NumPy, then builds the bundled ZX0 cruncher.
- `python3 -m pytest` runs all Python and assembly-equivalence tests. ACME is required for assembly tests.
- `python3 mkdisk.py --dir photos/` converts 2–18 images and creates `build/slideshow.d64` (it fails if the crunched slides overflow the disk's 664 blocks).
- `./go.sh [photo-directory]` performs setup if needed, builds the disk, and launches VICE.
- `python3 preview.py build/pic01.fli` previews a converted slide without starting the emulator.
- `python3 gen_tables.py` regenerates assembly includes in `build/gen/`; never edit those outputs manually.

## Coding Style & Naming Conventions

Use four-space indentation and standard Python conventions: `snake_case` for functions and variables, `PascalCase` for classes, and uppercase names for constants. Prefer `pathlib`, small pure functions, and explicit subprocess argument lists. Follow existing ACME formatting: lowercase labels and mnemonics, descriptive underscore-separated labels, and comments for cycle counts, memory ownership, or hardware constraints. Keep shell scripts POSIX-compatible (`#!/bin/sh`). No formatter or linter is configured, so match nearby code and keep diffs focused.

## Testing Guidelines

Pytest discovers files named `tests/test_*.py` and functions named `test_*`. Add regression tests beside the affected subsystem. For assembly routines, use `tests/asm_harness.py` to assemble snippets and execute them on the repository's 6502 core. There is no stated coverage threshold; prioritize conversion invariants, packed-format round trips, memory boundaries, and Python/assembly equivalence.

## Commit & Pull Request Guidelines

The short history uses concise, imperative summaries such as `Platform-aware setup + Linux/Windows (WSL) instructions`. Keep each commit scoped and describe the user-visible outcome. Pull requests should explain the motivation, list verification commands, and note PAL/VICE or real-hardware testing. Include preview images or screenshots for visual conversion, display, or transition changes, and call out any changes to generated assets or vendored loader code.
