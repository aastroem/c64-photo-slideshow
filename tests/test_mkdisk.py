import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import mkdisk


def test_sidecar_pin_beats_disk_default():
    assert mkdisk.effective_mode({"mode": "fli"}, "afli") == "fli"


def test_disk_default_applies_when_mode_unpinned():
    assert mkdisk.effective_mode({"sat": 1.2}, "afli") == "afli"


def test_falls_back_to_fli():
    assert mkdisk.effective_mode({}, "fli") == "fli"
