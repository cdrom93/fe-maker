import random

import pytest

from fe_maker import ups


def test_round_trip():
    rng = random.Random(1)
    source = bytes(rng.randrange(256) for _ in range(5000))
    target = bytearray(source)
    for i in (0, 1, 2, 100, 4999):
        target[i] ^= 0x5A
    target[2000:2010] = b"\0" * 10
    target = bytes(target)
    patch = ups.create(source, target)
    assert patch.startswith(b"UPS1")
    assert ups.apply(source, patch) == target


def test_identical_files():
    data = b"abc" * 100
    assert ups.apply(data, ups.create(data, data)) == data


def test_size_change():
    source, target = b"\1\2\3\4", b"\x01\x09\x03\x04\x05\x06"
    assert ups.apply(source, ups.create(source, target)) == target


def test_wrong_source_rejected():
    patch = ups.create(b"\1\2\3", b"\1\2\4")
    with pytest.raises(ups.UpsError):
        ups.apply(b"\x09\x09\x09", patch)
