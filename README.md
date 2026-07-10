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
- joystick-2 fire or space skips ahead (`SCANLINES=1 ./run_emulator.sh` for a CRT look)
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

### Prerequisites

You need four things; `setup.sh` checks them and prints the exact install
commands for your platform: the
[ACME](https://sourceforge.net/projects/acme-crossass/) cross-assembler,
[VICE](https://vice-emu.sourceforge.io) (`x64sc`, `c1541`), Python 3
(Pillow + numpy, installed by `setup.sh`), and a C compiler + make for the
bundled ZX0 cruncher.

**macOS**

```bash
brew install acme vice python
xcode-select --install        # C compiler, if you don't have it
./go.sh
```

**Linux** (Debian/Ubuntu shown; Arch/Fedora analogous)

```bash
sudo apt install acme vice build-essential python3 python3-pil python3-numpy
./go.sh
```

Note: Debian/Ubuntu ship VICE without the Commodore ROMs. Grab a VICE
release tarball from [vice-emu.sourceforge.io](https://vice-emu.sourceforge.io)
and copy its `C64/` ROM directory to `~/.local/share/vice/C64/` (or point
`VICE_DATADIR` at it). `c1541` and the build work without ROMs — only the
emulator needs them.

**Windows**

Use **WSL2** (Ubuntu) and follow the Linux steps above — on Windows 11 the
VICE window appears via WSLg automatically. Native Windows is possible
(ACME, VICE, and Python all have Windows builds, and the disk image
`build/slideshow.d64` is fully portable), but the helper scripts are POSIX
shell; you'd run the Python steps by hand and build `dali` with MSYS2/MinGW.
Easiest native route: build the `.d64` in WSL, then open it with the
Windows VICE — or write it straight to real hardware.

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
- `--pad 0-15` — side-bar color for portrait photos (default 0, black)

## Real hardware

Write `build/slideshow.d64` to a real disk (Ultimate 64 / 1541UII mount it
directly; ZoomFloppy + nibtools writes physical disks). Boot with
`LOAD"*",8,1` then `RUN`. PAL machines only. SD2IEC does **not** work — the
fast loader runs custom code in the 1541's drive CPU.

### FPGA cores / Analogue Pocket

The build also emits **`build/slideshow.g64`** — the same disk as a
GCR-level image, for devices whose 1541 emulation only accepts `.g64`, such
as the [MyC64 core](https://github.com/markus-zzz/myc64-pocket) for the
Analogue Pocket (load it via *Core Settings → Load G64 Slot*, then type
`LOAD"*",8,1` and `RUN`). The converter is `d64tog64.py` (pure Python, no
nibtools needed) and its output is verified to boot in VICE's GCR-level
drive emulation. Heads-up: the slideshow leans on cycle-exact VIC-II (FLI)
and drive timing (fast loader), which is demanding for work-in-progress
cores — a stock PAL C64 core in VICE-class accuracy is the reference.

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
