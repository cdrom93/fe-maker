"""UPS patch format (byuu's UPS1), the format FE Maker uses to share games.

Layout: "UPS1", varint source size, varint target size, then hunks of
(varint relative offset, XOR bytes terminated by 0x00), then CRC32 of the
source, the target and the patch itself (little endian).
"""

from __future__ import annotations

import struct
import zlib


class UpsError(Exception):
    pass


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        x = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        value -= 1


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    value, shift = 0, 1
    while True:
        if pos >= len(data):
            raise UpsError("Truncated patch")
        x = data[pos]
        pos += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def create(source: bytes, target: bytes) -> bytes:
    out = bytearray(b"UPS1")
    out += _encode_varint(len(source))
    out += _encode_varint(len(target))
    length = max(len(source), len(target))
    pos = last = 0
    while pos < length:
        s = source[pos] if pos < len(source) else 0
        t = target[pos] if pos < len(target) else 0
        if s == t:
            pos += 1
            continue
        out += _encode_varint(pos - last)
        while pos < length:
            s = source[pos] if pos < len(source) else 0
            t = target[pos] if pos < len(target) else 0
            if s == t:
                break
            out.append(s ^ t)
            pos += 1
        out.append(0)
        pos += 1
        last = pos
    out += struct.pack("<II", zlib.crc32(source), zlib.crc32(target))
    out += struct.pack("<I", zlib.crc32(bytes(out)))
    return bytes(out)


def apply(source: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"UPS1" or len(patch) < 16:
        raise UpsError("Not a UPS patch")
    if zlib.crc32(patch[:-4]) != struct.unpack("<I", patch[-4:])[0]:
        raise UpsError("Corrupted patch")
    src_crc, tgt_crc = struct.unpack("<II", patch[-12:-4])
    if zlib.crc32(source) != src_crc:
        raise UpsError("This patch is for a different ROM")
    pos = 4
    src_size, pos = _decode_varint(patch, pos)
    tgt_size, pos = _decode_varint(patch, pos)
    target = bytearray(source[:tgt_size].ljust(tgt_size, b"\0"))
    out_pos, end = 0, len(patch) - 12
    while pos < end:
        skip, pos = _decode_varint(patch, pos)
        out_pos += skip
        while True:
            x = patch[pos]
            pos += 1
            if x == 0:
                break
            if out_pos < tgt_size:
                target[out_pos] ^= x
            out_pos += 1
        out_pos += 1
    if zlib.crc32(bytes(target)) != tgt_crc:
        raise UpsError("Patched ROM checksum mismatch")
    return bytes(target)
