# c64-photo-slideshow

Turn your photos into a bootable **Commodore 64 slideshow** on a real
1541-compatible disk. Photos are converted to multicolor **FLI** (the C64
demoscene's high-color bitmap mode) with perceptual color matching and
dithering, packed onto a `.d64` with music and dissolve transitions, and
displayed by cycle-exact 6502 code.

![sample conversions](docs/img/samples.png)

- 2–11 photos per disk (ZX0-compressed, loaded by Krill's fast loader)
- slides melt into each other with a randomized cell dissolve — the next
  photo loads *underneath* the running FLI display, so there are no black
  screens, fades, or degraded frames, ever
- in-house 3-voice SID tune plays throughout (swap in your own)
- joystick-2 fire or space skips ahead
- portrait photos are auto-fitted with colored side bars
- slide order: a file named `01.*` goes first, the rest follow EXIF capture time
- runs on real hardware (PAL C64 + 1541, Ultimate 64, 1541UII) and in VICE

## Quick start

```bash
./go.sh                 # sample photos -> disk image -> VICE
./go.sh my-photos/      # your own directory of 2-11 images
```

`go.sh` runs `setup.sh` on first use, which checks prerequisites and builds
the bundled ZX0 cruncher.

### Prerequisites (macOS)

| What | Install |
|---|---|
| [ACME](https://sourceforge.net/projects/acme-crossass/) cross-assembler | `brew install acme` |
| [VICE](https://vice-emu.sourceforge.io) emulator (`x64sc`, `c1541`) | `brew install vice` |
| Python 3 with Pillow + numpy | `brew install python`, rest via `setup.sh` |
| C compiler + make (for the cruncher) | `xcode-select --install` |

Linux works too with the same tools from your package manager
(`acme`, `vice`, `python3-pil`, `python3-numpy`, `build-essential`).

## Using your own photos

Drop 2–11 JPG/PNG images into a directory and `./go.sh that-dir/`. Each
photo gets a JSON sidecar remembering its conversion settings; tune any
photo and rebuild:

```bash
python3 convert.py my-photos/beach.jpg --dither fs --strength 0.7 --sat 1.2 --crop 0,-0.4
python3 preview.py build/pic03.fli        # judge quality without a C64
python3 mkdisk.py --dir my-photos/        # rebuilds only what changed
```

- `--dither fs|bayer4|bayer8|hybrid` — error diffusion (detail), ordered
  (calm skies), or hybrid (default: ordered in flat areas, FS at edges)
- `--strength`, `--sat`, `--gamma` — dither amount, saturation, gamma
- `--crop dx,dy` — shift the crop window (−1..1)
- `--pad 0-15` — side-bar color for portrait photos (default 11, dark grey)

## Real hardware

Write `build/slideshow.d64` to a real disk (Ultimate 64 / 1541UII mount it
directly; ZoomFloppy + nibtools writes physical disks). Boot with
`LOAD"*",8,1` then `RUN`. PAL machines only. SD2IEC does **not** work — the
fast loader runs custom code in the 1541's drive CPU.

The music lives in `src/music.asm` as three simple `note,duration` streams —
easy to replace with your own tune.

## How it works

The short version: photos are matched against the measured C64 palette in
OkLab color space, attributes are optimized per FLI color slot, and the
result is packed into a trimmed format that a 6502 routine unpacks in place.
On the C64, a stable-raster IRQ forces a *late* badline on every scanline
(the trick that makes FLI work — and causes its famous unusable left
columns), while Krill's loader streams the next picture in underneath.
The gory details, including several hard-won hardware facts, are in
[TECHNICAL.md](TECHNICAL.md).

## Credits

- **Loader by [Krill](https://csdb.dk/scener/?id=8104)** — the vendored
  [Krill's Loader, repository version 194](https://csdb.dk/release/?id=226124)
  does all disk I/O and on-the-fly ZX0 decompression (see
  `src/loader/VERSION` and its license in `src/loader/loader/README`)
- **ZX0** compression format by Einar Saukas; crunched with **dali** /
  **salvador** by Emmanuel Marty (bundled with Krill's loader)
- **Pepto's** measured VIC-II palette (Philip Timmermann,
  [pepto.de/projects/colorvic](https://www.pepto.de/projects/colorvic/))
- **ACME** cross-assembler and **VICE** emulator teams
- Sample photos served by [picsum.photos](https://picsum.photos)
  (Unsplash-licensed images)
- Built by [aastroem](https://github.com/aastroem) with
  [Claude](https://claude.com) (Anthropic's Claude Code) doing the heavy
  lifting — from the OkLab converter to the cycle-exact FLI displayer

## License

MIT for everything in this repository except the vendored third-party code
under `src/loader/` — see [LICENSE](LICENSE).
