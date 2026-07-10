#!/bin/sh
# Launch the slideshow in VICE (real-time, sound on, cycle-exact 1541).
# Autostart types LOAD/RUN itself -- don't touch the keyboard during the
# first ~30 seconds while the drive boots the program.
cd "$(dirname "$0")"
exec x64sc -drive8truedrive -autostart build/slideshow.d64
