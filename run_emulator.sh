#!/bin/sh
# Launch the slideshow in VICE (real-time, sound on, cycle-exact 1541).
# SCANLINES=1 adds CRT emulation with scanline shading.
# Autostart types LOAD/RUN itself -- don't touch the keyboard during the
# first ~30 seconds while the drive boots the program.
cd "$(dirname "$0")"
if [ "${SCANLINES:-0}" = "1" ]; then FILTER="-VICIIfilter 1 -VICIIcrtscanlineshade 600"; else FILTER=""; fi
exec x64sc -drive8truedrive $FILTER -autostart build/slideshow.d64
