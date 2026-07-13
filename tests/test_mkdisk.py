import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import mkdisk


def test_sidecar_pin_beats_disk_default():
    assert mkdisk.effective_mode({"mode": "fli"}, "afli") == "fli"


def test_disk_default_applies_when_mode_unpinned():
    assert mkdisk.effective_mode({"sat": 1.2}, "afli") == "afli"


def test_falls_back_to_fli():
    assert mkdisk.effective_mode({}, "fli") == "fli"


def test_over_capacity_raises_with_detail():
    with pytest.raises(SystemExit) as e:
        mkdisk.check_capacity(700, "boot 16, main 23, pics 300+361", "afli")
    msg = str(e.value)
    assert "700/664" in msg          # the numbers, not just "over capacity"
    assert "pics 300+361" in msg     # which slides are the fat ones
    assert "afli" in msg             # what mode produced them


def test_within_capacity_is_silent():
    assert mkdisk.check_capacity(318, "boot 16, main 23, pics 19+35", "fli") is None
