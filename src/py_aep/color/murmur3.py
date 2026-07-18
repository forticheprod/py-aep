"""MurmurHash3 (x64, 128-bit) - the hash After Effects uses to derive the 16-byte
`Guid` (UID) of a color space.

After Effects identifies an OCIO output color space by a 16-byte id stored in the
render-queue output module (`output_profile_id`). That id is the color space's
`dvamediatypes::color::ColorSpace` `Guid`, computed as a two-stage MurmurHash3
(see `dvacore::utility::Murmur3MixerState`), reverse-engineered from
`dvamediatypes.dll` / `dvacore.dll`. The only non-standard detail is the seed:
AE initializes both 64-bit accumulators with `0xC29DE5B8264CD69E` instead of 0.

This module is the standard `MurmurHash3_x64_128` (Austin Appleby), parameterized
by that seed.
"""

from __future__ import annotations

_MASK = (1 << 64) - 1
_C1 = 0x87C37B91114253D5
_C2 = 0x4CF5AD432745937F

#: The seed After Effects loads into both accumulators (dvacore Murmur3MixerState).
DVA_SEED = 0xC29DE5B8264CD69E


def _rotl64(x: int, r: int) -> int:
    return ((x << r) | (x >> (64 - r))) & _MASK


def _fmix64(k: int) -> int:
    k ^= k >> 33
    k = (k * 0xFF51AFD7ED558CCD) & _MASK
    k ^= k >> 33
    k = (k * 0xC4CEB9FE1A85EC53) & _MASK
    k ^= k >> 33
    return k


def murmurhash3_x64_128(data: bytes, seed: int = 0) -> bytes:
    """Return the 16-byte MurmurHash3 x64 128-bit digest of `data`.

    `seed` initializes both 64-bit accumulators (After Effects uses
    [DVA_SEED][py_aep.color.murmur3.DVA_SEED]). The output is `h1` then `h2`,
    each little-endian - the byte order After Effects stores in a `Guid`.
    """
    h1 = seed & _MASK
    h2 = seed & _MASK
    length = len(data)
    nblocks = length // 16
    for i in range(nblocks):
        k1 = int.from_bytes(data[i * 16 : i * 16 + 8], "little")
        k2 = int.from_bytes(data[i * 16 + 8 : i * 16 + 16], "little")
        k1 = (_rotl64((k1 * _C1) & _MASK, 31) * _C2) & _MASK
        h1 ^= k1
        h1 = _rotl64(h1, 27)
        h1 = (h1 + h2) & _MASK
        h1 = (h1 * 5 + 0x52DCE729) & _MASK
        k2 = (_rotl64((k2 * _C2) & _MASK, 33) * _C1) & _MASK
        h2 ^= k2
        h2 = _rotl64(h2, 31)
        h2 = (h2 + h1) & _MASK
        h2 = (h2 * 5 + 0x38495AB5) & _MASK
    tail = data[nblocks * 16 :]
    k1 = 0
    k2 = 0
    tl = len(tail)
    if tl >= 15:
        k2 ^= tail[14] << 48
    if tl >= 14:
        k2 ^= tail[13] << 40
    if tl >= 13:
        k2 ^= tail[12] << 32
    if tl >= 12:
        k2 ^= tail[11] << 24
    if tl >= 11:
        k2 ^= tail[10] << 16
    if tl >= 10:
        k2 ^= tail[9] << 8
    if tl >= 9:
        k2 ^= tail[8]
        k2 = (_rotl64((k2 * _C2) & _MASK, 33) * _C1) & _MASK
        h2 ^= k2
    if tl >= 8:
        k1 ^= tail[7] << 56
    if tl >= 7:
        k1 ^= tail[6] << 48
    if tl >= 6:
        k1 ^= tail[5] << 40
    if tl >= 5:
        k1 ^= tail[4] << 32
    if tl >= 4:
        k1 ^= tail[3] << 24
    if tl >= 3:
        k1 ^= tail[2] << 16
    if tl >= 2:
        k1 ^= tail[1] << 8
    if tl >= 1:
        k1 ^= tail[0]
        k1 = (_rotl64((k1 * _C1) & _MASK, 31) * _C2) & _MASK
        h1 ^= k1
    h1 ^= length
    h2 ^= length
    h1 = (h1 + h2) & _MASK
    h2 = (h2 + h1) & _MASK
    h1 = _fmix64(h1)
    h2 = _fmix64(h2)
    h1 = (h1 + h2) & _MASK
    h2 = (h2 + h1) & _MASK
    return h1.to_bytes(8, "little") + h2.to_bytes(8, "little")


def dva_guid(data: bytes) -> bytes:
    """Return the 16-byte After Effects `Guid` for `data` (MurmurHash3 x64 128
    with After Effects' [DVA_SEED][py_aep.color.murmur3.DVA_SEED])."""
    return murmurhash3_x64_128(data, DVA_SEED)
