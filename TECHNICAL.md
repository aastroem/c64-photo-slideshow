# Technical notes

Bootable d64: 2-11 photos as multicolor FLI (ZX0-crunched, Krill loadcompd),
image-to-image dissolve transitions. Loads happen with the FLI display ON —
the outgoing image stays pixel-perfect (the earlier MC-degrade fallback made
FLI line-0 colors bleed across cell rows: white speckle everywhere; and the
fade-to-black variant was dropped). The display IRQ costs ~2/3 CPU
during loads, which just makes them slower — Krill v194 tolerates the long
handler fine. SID music, PAL only. Built by `mkdisk.py`
(`--dir photos/kenneth`; order = 01.* first, then EXIF time; portraits
padded with `pad` sidecar color). Design spec in
`the repo history`.
`src/fade.asm` (luminance fade, tested) is kept but not linked. Loader zp is
$e0-$ef with ZX0 resident ($0200-$0406) — music zp moved to $50-$55, display
savesp $57.

## Memory map (runtime)

```
$0200-$02DF  Krill resident (loadraw = $0200); zp $e0-$e4
$0900-$3FFF  MAIN prg: state machine, IRQ/FLI displayer (unrolled 199 lines),
             music, unpack, fade, dissolve, Fisher-Yates order gen
$4000-$7FFF  VIC bank A (displayed): screens $4000+i*$400, bitmap $6000
$8000-$BFFF  VIC bank B: pics load here ($8000, FLIP format), unpack in place
$C000-$C3E7  color-RAM staging for incoming pic
$C400/$C800  dissolve order tables (1000 x lo/hi), generated at runtime
```

Boot chain: "SLIDESHOW" (KERNAL load, $0801-$1676: stub + install blob at
$0900 + resident blob) → jsr install → SEI forever → copy resident to $0200
→ loadraw "MAIN" ($0900, overwrites spent install) → jmp $0900.

## FLIP file format (15727 bytes, fits 10 pics + code on one d64 side)

2-byte load addr $8000, then screens 8×25×37, bitmap 25×37×8, color 25×37 —
columns 0-2 (FLI bug) are omitted and always black. Backwards in-place
6502 unpacker expands to bank layout (every source byte sits below its
target). Python reference: `fli.unpack_to_ram`; equivalence-tested against
the asm on tools/cpu6502.py.

## FLI display — the actual working timing

- Image line n displays at raster 51+n (RSEL border opens at 51).
  d011 = $38|((3+n)&7), d018 = ((n&7)<<4)|$08, per line, 23-cycle unrolled
  blocks (badline leaves the CPU 23 cycles/line).
- **Badlines must be LATE**: the d011 write lands cycle ~15-16, after the
  VIC's cycle-14 check. Early badlines reset RC every line → VCBASE never
  advances → every line reads screen row 0. Late badlines leave RC free-
  running 0-7, which advances VCBASE every 8th line (and causes the FLI bug
  in columns 0-2 — hence black there). Line 0 gets a normal (early) badline
  (yscroll 3 armed ahead) to init RC=0.
- Entry sync: double-IRQ stabilizer, then a nop carpet into the raster-51
  badline halt — the halt itself aligns the loop; ENTRY_LOOPS=30 calibrated
  by sweeping in VICE against a row+bank-sensitive test pattern (a uniform
  stripe pattern CANNOT detect row-counter bugs — it validates only d018).
- Lines 197-199 (rasters 248-250, past the badline window) reuse line 196's
  screen colors: a hardware fact of FLI. The converter therefore optimizes
  lines 196-199 jointly and emits one shared screen byte per cell for them,
  so the display is pixel-identical to the converter's output anyway.
- Line 1 (the first LATE badline) follows line 0's normal badline, whose
  halt window differs by ~1 cycle from steady state, widening the FLI bug
  into char column 3 on that single line (4 multicolor pixels). Trimming
  the first unrolled block by 1 cycle fixes it on paper but halves the
  timing margin -- residual frame-to-frame IRQ jitter then flips line 1
  into an occasional EARLY badline (row-counter reset = visibly shaky
  frames), so it was reverted. A truly jitter-free stabilizer would allow
  it; until then those 4 static pixels are the accepted imperfection.
- Verified pixel-exact against preview.py in VICE (0 mismatches on lines
  2-199 incl. the badline-window tail; 4 known pixels on line 1, above;
  VICE renders a brightened palette — extract it empirically from a
  probe screenshot, don't trust the .vpl values for comparisons).

## Krill's loader v194 — integration rules (each one cost blood)

- Prebuilt binaries are huge (all drive families + ZX0). Rebuilt with ca65:
  ONLY_1541_AND_COMPATIBLE=1, no decompressor → install 3.2K, resident 224B.
- **$DD00: upper 6 bits must be written as 0** while the loader is resident
  (`lda #$02 / sta $dd00` for bank $4000). Never RMW $DD00 — reading PA
  returns live IEC lines; writing them back wedges the bus mid-transfer
  (symptom: load sprays over wrong addresses / stalls forever).
- Resident at $0200 overlaps the KERNAL keyboard buffer ($0277+) and RS-232
  vars ($0293-$02A1): SEI immediately after install returns and never touch
  KERNAL again. A stray keyboard IRQ corrupts the resident; a later KERNAL
  IEC call spins forever at $F0AA on the blob byte at $02A1 (ENABL).
- The IRQ (FLI display + music) runs fine during loads (v194 is
  interruptible); loads happen on a blanked screen anyway.
- Music player zp $e8-$ed, display $e6, effects $f7-$fa — loader owns
  $e0-$e4 only with this build.

## VICE verification traps

- `-truedrive` doesn't exist: use `-drive8truedrive`.
- Real-time (no warp) `-autostart` works fine — use `run_emulator.sh`.
- Autostart/keybuf under WARP+truedrive silently drops the RUN Return.
  Workaround: `-keybuf 'load"*",8,1\n'`, wait for READY, then poke RUN via
  remote monitor (`> 0277 52 55 4e 0d`, `> 00c6 04`) ONCE — and hands off:
  **NEVER poke the keyboard buffer after the program started: $0277-$0280
  is inside the resident loader; the poke stamps "RUN" over its code and
  the machine jams (opcode $52) on a later load. Cost hours. Twice.**
  every remote-monitor connection freezes the C64 while the drive keeps
  running, breaching the loader protocol (watchdog resets the drive).
  Only connect the monitor when the IEC bus is idle (show phase / READY).
- x64sc PNG geometry: display pixel (0,0) at (32, raster-16); screenshots
  via monitor `screenshot "file" 2`.
