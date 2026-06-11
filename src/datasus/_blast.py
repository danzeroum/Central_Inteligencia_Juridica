"""Pure-Python PKWARE Blast (DCL Implode) decompressor.

Faithful port of blast.c by Mark Adler (zlib/contrib/blast/blast.c, public domain).
Used by DATASUS to produce .dbc files (DBF compressed with PKWARE DCL Implode).

Reference: https://github.com/madler/zlib/blob/master/contrib/blast/blast.c

Public API
----------
decompress(data: bytes) -> bytes
"""

from __future__ import annotations

_MAXBITS = 13
_MAXWIN = 4096

# Length base values and extra bits (blast.c: base[], extra[])
_LENBASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
_LENEXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]

# Distance base values and extra bits for dict=0 (1K window)
# For dict>0 the distance is encoded directly; see _decode_dist().
_DISBASE = [
    1,
    2,
    3,
    4,
    6,
    8,
    12,
    16,
    24,
    32,
    48,
    64,
    96,
    128,
    192,
    256,
    384,
    512,
    768,
    1024,
    1536,
    2048,
    3072,
    4096,
    6144,
    8192,
    12288,
    16384,
    24576,
]
_DISEXTRA = [
    0,
    0,
    0,
    0,
    1,
    1,
    2,
    2,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
    7,
    8,
    8,
    9,
    9,
    10,
    10,
    11,
    11,
    12,
    12,
    13,
]

# ── Fixed Huffman tables (blast.c static data) ─────────────────────────────
#
# litlen[i] = bit length of the fixed code for literal byte i (256 entries).
# Derived from the run-length pairs in blast.c litlen[] via construct().
# DATASUS files typically use lit=1 (ASCII mode), so these are only used
# when the compressed stream sets lit=0.
_LITLEN: list[int] = [
    # 0x00-0x0F (control)
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    9,
    10,
    11,
    11,
    10,
    11,
    11,
    # 0x10-0x1F
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    11,
    # 0x20-0x2F (space, punctuation)
    5,
    7,
    8,
    7,
    7,
    7,
    7,
    7,
    6,
    7,
    7,
    7,
    7,
    6,
    7,
    7,
    # 0x30-0x3F (digits, colon, semicolon…)
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    7,
    7,
    7,
    7,
    7,
    7,
    # 0x40-0x4F (@ A-O)
    7,
    5,
    5,
    5,
    5,
    4,
    5,
    5,
    5,
    4,
    6,
    5,
    5,
    5,
    5,
    5,
    # 0x50-0x5F (P-Z, brackets)
    5,
    6,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    5,
    6,
    7,
    7,
    7,
    7,
    7,
    # 0x60-0x6F (` a-o)
    7,
    4,
    5,
    4,
    4,
    4,
    5,
    4,
    5,
    4,
    6,
    5,
    5,
    4,
    4,
    4,
    # 0x70-0x7F (p-z, braces, DEL)
    5,
    6,
    5,
    4,
    4,
    5,
    5,
    5,
    5,
    5,
    6,
    7,
    7,
    7,
    7,
    11,
    # 0x80-0xFF (extended) — all length 8 or 9
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
    9,
]

# lenlen[i] = bit length of the fixed code for length symbol i (16 entries).
_LENLEN: list[int] = [2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5]

# dislen[i] = bit length of the fixed code for distance symbol i, dict=0 (29 entries).
_DISLEN: list[int] = [
    3,
    4,
    4,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    6,
    6,
    6,
    6,
    6,
    7,
    7,
    7,
    7,
    7,
    7,
    7,
    7,
    8,
    8,
    8,
    8,
    8,
    8,
]


# ── Huffman helpers ─────────────────────────────────────────────────────────


def _build_table(lengths: list[int]) -> tuple[list[int], list[int]]:
    """Build canonical Huffman decode table (count[], symbol[]).

    count[i] = number of codes of length i (1-indexed).
    symbol[] = symbols in canonical order (shortest first).
    """
    n = len(lengths)
    count: list[int] = [0] * (_MAXBITS + 1)
    for ln in lengths:
        if 0 < ln <= _MAXBITS:
            count[ln] += 1

    symbol: list[int] = [0] * n
    offs: list[int] = [0] * (_MAXBITS + 2)
    offs[1] = 0
    for i in range(1, _MAXBITS + 1):
        offs[i + 1] = offs[i] + count[i]

    for sym in range(n):
        ln = lengths[sym]
        if ln:
            symbol[offs[ln]] = sym
            offs[ln] += 1

    return count, symbol


def _decode(bitbuf: int, bitcnt: int, count: list[int], symbol: list[int]) -> int:
    """Decode one symbol from the bit buffer (does NOT consume bits itself).

    Returns (symbol_value, bits_consumed).
    """
    code = 0
    first = 0
    index = 0
    for length in range(1, _MAXBITS + 1):
        if bitcnt < length:
            raise ValueError("blast: not enough bits for Huffman decode")
        bit = (bitbuf >> (length - 1)) & 1
        code = (code << 1) | bit
        cnt = count[length]
        if code - cnt < first:
            return symbol[index + (code - first)], length
        index += cnt
        first = (first + cnt) << 1
    raise ValueError("blast: invalid Huffman code")


# ── Bit reader ──────────────────────────────────────────────────────────────


class _Bits:
    """LSB-first bit reader over a bytes buffer."""

    __slots__ = ("data", "pos", "buf", "cnt")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.buf = 0
        self.cnt = 0

    def read(self, n: int) -> int:
        while self.cnt < n:
            if self.pos >= len(self.data):
                raise ValueError("blast: premature end of input")
            self.buf |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        val = self.buf & ((1 << n) - 1)
        self.buf >>= n
        self.cnt -= n
        return val

    def peek(self, n: int) -> int:
        """Peek at n bits without consuming."""
        while self.cnt < n:
            if self.pos >= len(self.data):
                raise ValueError("blast: premature end of input")
            self.buf |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        return self.buf & ((1 << n) - 1)

    def consume(self, n: int) -> None:
        self.buf >>= n
        self.cnt -= n


# ── Main decompressor ───────────────────────────────────────────────────────


def decompress(data: bytes) -> bytes:
    """Decompress PKWARE Blast (DCL Implode) compressed bytes.

    Args:
        data: raw compressed bytes (after any DBC file header stripping).

    Returns:
        Decompressed bytes.

    Raises:
        ValueError: on malformed input.
    """
    bits = _Bits(data)

    # Header: 1-bit lit (0=Huffman, 1=ASCII), 2-bit dict (0=1K, 1=2K, 2=4K, 3=8K)
    lit = bits.read(1)
    dict_exp = bits.read(2)  # 0→1K, 1→2K, 2→4K, 3→8K
    dict_bits = dict_exp + 6  # extra bits for distance: 6, 7, 8, 9

    # Build Huffman tables
    lit_count, lit_sym = _build_table(_LITLEN)
    len_count, len_sym = _build_table(_LENLEN)
    dis_count, dis_sym = _build_table(_DISLEN)

    win = bytearray(_MAXWIN)
    wpos = 0
    out = bytearray()

    while True:
        if bits.read(1):
            # ── Back-reference ────────────────────────────────────────────
            # Decode length symbol (0-15)
            lraw = bits.peek(_MAXBITS)
            lsym, lbits = _decode(lraw, _MAXBITS, len_count, len_sym)
            bits.consume(lbits)
            length = _LENBASE[lsym] + bits.read(_LENEXTRA[lsym])

            if dict_exp == 0:
                # Small dict (1K): decode distance using Huffman
                draw = bits.peek(_MAXBITS)
                dsym, dbits = _decode(draw, _MAXBITS, dis_count, dis_sym)
                bits.consume(dbits)
                dist = _DISBASE[dsym] + bits.read(_DISEXTRA[dsym])
            else:
                # Larger dict: distance encoded directly
                lo = bits.read(6)
                hi = bits.read(dict_bits)
                dist = lo | (hi << 6)
                dist += 1

            for _ in range(length):
                src = (wpos - dist) % _MAXWIN
                byte = win[src]
                win[wpos] = byte
                wpos = (wpos + 1) % _MAXWIN
                out.append(byte)

        else:
            # ── Literal ───────────────────────────────────────────────────
            if lit:
                symbol = bits.read(8)
            else:
                raw = bits.peek(_MAXBITS)
                symbol, nbits = _decode(raw, _MAXBITS, lit_count, lit_sym)
                bits.consume(nbits)

            if symbol == 519:
                break  # end-of-block marker (blast)

            win[wpos] = symbol
            wpos = (wpos + 1) % _MAXWIN
            out.append(symbol)

    return bytes(out)
