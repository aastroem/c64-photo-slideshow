#!/usr/bin/env python3
"""Convert a standard 35-track .d64 into a .g64 (GCR-level disk image).

    python3 d64tog64.py build/slideshow.d64 [-o build/slideshow.g64]

Some devices emulate the 1541 at the magnetic-flux level and only accept
.g64 (e.g. the MyC64 core for the Analogue Pocket). For a standard CBM DOS
disk the conversion is deterministic: each sector is GCR-encoded with the
stock header/data layout and zone-correct track sizing. Output is verified
to boot identically in VICE, whose drive emulation reads the GCR directly.
"""

import argparse
import pathlib
import struct

GCR = [0x0A, 0x0B, 0x12, 0x13, 0x0E, 0x0F, 0x16, 0x17,
       0x09, 0x19, 0x1A, 0x1B, 0x0D, 0x1D, 0x1E, 0x15]

# tracks per speed zone: (first_track, sectors, raw_track_capacity)
ZONES = [(1, 21, 7692), (18, 19, 7142), (25, 18, 6666), (31, 17, 6250)]
MAX_TRACK = 7928


def zone(track):
    for start, sectors, cap in reversed(ZONES):
        if track >= start:
            return sectors, cap, 3 - ZONES.index((start, sectors, cap))


def gcr_encode(data):
    """4 data bytes -> 5 GCR bytes, over the whole buffer (len % 4 == 0)."""
    out = bytearray()
    for i in range(0, len(data), 4):
        bits = 0
        for b in data[i:i + 4]:
            bits = (bits << 10) | (GCR[b >> 4] << 5) | GCR[b & 15]
        out += bits.to_bytes(5, "big")
    return bytes(out)


def encode_track(track, sectors, cap, disk_id, sector_data):
    id1, id2 = disk_id
    out = bytearray()
    body = 5 + 10 + 9 + 5 + 325                    # sync+hdr+gap+sync+data
    tail = max(8, (cap - sectors * body) // sectors)
    for s in range(sectors):
        hdr = bytes([0x08, s ^ track ^ id2 ^ id1, s, track, id2, id1, 0x0F, 0x0F])
        blk = sector_data[s]
        cks = 0
        for b in blk:
            cks ^= b
        data = bytes([0x07]) + blk + bytes([cks, 0, 0])
        out += b"\xff" * 5 + gcr_encode(hdr)       # sync + header
        out += b"\x55" * 9                          # header gap
        out += b"\xff" * 5 + gcr_encode(data)      # sync + data block
        out += b"\x55" * tail                       # inter-sector gap
    return bytes(out)


def convert(d64_path, g64_path):
    d64 = pathlib.Path(d64_path).read_bytes()
    assert len(d64) in (174848, 175531), "expected a standard 35-track d64"

    # sector offsets in the d64
    offsets, off = {}, 0
    for t in range(1, 36):
        sectors, _, _ = zone(t)
        offsets[t] = off
        off += sectors * 256
    disk_id = (d64[offsets[18] + 0xA2], d64[offsets[18] + 0xA3])

    tracks = []
    for t in range(1, 36):
        sectors, cap, _ = zone(t)
        data = [d64[offsets[t] + s * 256: offsets[t] + (s + 1) * 256]
                for s in range(sectors)]
        tracks.append(encode_track(t, sectors, cap, disk_id, data))

    hdr = b"GCR-1541" + bytes([0, 84]) + struct.pack("<H", MAX_TRACK)
    track_off = bytearray()
    speed_off = bytearray()
    body = bytearray()
    base = len(hdr) + 84 * 4 * 2
    for i in range(84):
        t = i // 2 + 1
        if i % 2 == 0 and t <= 35:
            track_off += struct.pack("<I", base + len(body))
            _, _, spd = zone(t)
            speed_off += struct.pack("<I", spd)
            raw = tracks[t - 1]
            body += struct.pack("<H", len(raw)) + raw.ljust(MAX_TRACK, b"\x55")
        else:
            track_off += struct.pack("<I", 0)
            speed_off += struct.pack("<I", 0)
    pathlib.Path(g64_path).write_bytes(hdr + track_off + speed_off + body)
    print(f"wrote {g64_path} ({(len(hdr)+len(track_off)+len(speed_off)+len(body))//1024}K)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("d64", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path)
    args = ap.parse_args()
    convert(args.d64, args.out or args.d64.with_suffix(".g64"))


if __name__ == "__main__":
    main()
