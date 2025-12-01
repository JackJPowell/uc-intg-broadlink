"""
Unified IR code conversion utilities for Broadlink devices.

Supported input formats:
- PRONTO 0000 (treat all timings as one block, drop last if odd; no repeat expansion)
- Global Caché 'sendir' strings
- Custom NEC format: "3;0x<hex>;bits;repeat_count"
- Raw list[int] pulses in microseconds (already normalized)
- BroadLink raw HEX payload (starts with 0x26...) passthrough

Public main entry point for BroadLink packet creation:
    convert_to_broadlink(code)

Convenience helpers:
    pronto_to_broadlink(pronto_hex)
    hex_to_broadlink(hex_string)
"""

from __future__ import annotations

import binascii
import logging
import re
from typing import List, Union

_LOG = logging.getLogger(__name__)

# BroadLink tick (≈32.84µs)
BRDLNK_UNIT = 269.0 / 8192.0

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _clean_hex(s: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", s)


def _looks_like_broadlink_hex(s: str) -> bool:
    stripped = re.sub(r"\s+", "", s)
    if len(stripped) < 4 or len(stripped) % 2 != 0:
        return False
    if not re.fullmatch(r"[0-9A-Fa-f]+", stripped):
        return False
    # BroadLink IR payloads typically start with 0x26
    return stripped.lower().startswith("26")


def _round_half_up(x: float) -> int:
    """
    Round half up for non-negative values.
    """
    if x <= 0:
        return 0
    return int(x + 0.5)


# ---------------------------------------------------------------------------
# BroadLink raw HEX passthrough
# ---------------------------------------------------------------------------


def hex_to_broadlink(hex_string: str) -> bytes:
    """
    Treat the given HEX string as an already BroadLink-ready payload (raw bytes).
    Returns the decoded bytes.
    """
    cleaned = _clean_hex(hex_string)
    if len(cleaned) == 0 or len(cleaned) % 2 != 0:
        raise ValueError("HEX: invalid length for BroadLink passthrough")
    try:
        return binascii.unhexlify(cleaned)
    except binascii.Error as e:
        raise ValueError(f"HEX: decode error: {e}") from e


# ---------------------------------------------------------------------------
# Global Caché 'sendir' parsing
# ---------------------------------------------------------------------------


def gc_to_pulses(gc_str: str) -> List[int]:
    """
    Convert Global Caché 'sendir' string into microsecond pulses.
    Example: "sendir,1:1,1,38000,1,1,343,171,21,21,..."
    """
    parts = gc_str.strip().split(",")
    if not parts[0].lower().startswith("sendir"):
        raise ValueError("Not a Global Caché sendir string")

    freq = int(parts[3])  # Hz
    unit_micros = 1_000_000 / freq
    pulse_counts = list(map(int, parts[6:]))
    return [round(c * unit_micros) for c in pulse_counts]


# ---------------------------------------------------------------------------
# NEC custom builder
# ---------------------------------------------------------------------------


def nec_to_pulses(code_str: str, lsb_first: bool = False) -> List[int]:
    """
    Convert custom NEC IR code format to pulse data.

    Format: <protocol>;<hex-ir-code>;<bits>;<repeat-count>
    Example: "3;0x1FE50AF;32;2"
    """
    try:
        proto, hex_code, nbits, repeat = code_str.split(";")
        proto = int(proto)
        if proto != 3:
            raise ValueError("Only NEC (protocol=3) supported.")
        code = int(hex_code, 16)
        nbits = int(nbits)
        repeat = int(repeat)
    except Exception as e:
        raise ValueError(f"Invalid code string '{code_str}': {e}") from e

    tick = 560
    header_mark = 16 * tick
    header_space = 8 * tick
    one_space = 3 * tick
    zero_space = 1 * tick

    pulses: List[int] = [header_mark, header_space]

    for i in range(nbits):
        bit = (code >> i) & 1 if lsb_first else (code >> (nbits - 1 - i)) & 1
        pulses.append(tick)
        pulses.append(one_space if bit else zero_space)

    pulses.append(tick)  # final mark

    frame_len = 108_000
    gap = frame_len - sum(pulses)
    if gap > 0:
        pulses.append(gap)

    full = pulses[:]
    for _ in range(repeat):
        rep = [16 * tick, 4 * tick, tick]
        rep_gap = frame_len - sum(rep)
        if rep_gap > 0:
            rep.append(rep_gap)
        full += rep

    return full


# ---------------------------------------------------------------------------
# PRONTO (0000) parsing → BroadLink bytes
# ---------------------------------------------------------------------------


def _hex_to_words(pronto_hex: str) -> List[int]:
    """
    PRONTO string -> array of 16-bit words. Tolerates non-hex separators.
    Requires total hex length to be a positive multiple of 4.
    """
    cleaned = _clean_hex(pronto_hex)
    if len(cleaned) == 0 or len(cleaned) % 4 != 0:
        raise ValueError("PRONTO: hex length must be positive and multiple of 4")
    return [int(cleaned[i : i + 4], 16) for i in range(0, len(cleaned), 4)]


def pronto_to_broadlink(pronto_hex: str) -> bytes:
    """
    Convert PRONTO 0000 code to BroadLink RM payload (bytes), matching the JavaScript logic:

      - Only learned format 0000 is supported
      - Treat all timings after the first 4 words as a single block
      - If an odd number of timing words is present, drop the last value
      - Microseconds per unit = freq_word * 0.241246, rounded with half-up
      - BroadLink ticks = floor(us * 269 / 8192)
      - Pack as: 0x26 0x00 [len_lo] [len_hi] [payload...] 0x0d 0x05
      - Pad to a multiple of 16 bytes with zeros
    """
    words = _hex_to_words(pronto_hex)

    if len(words) < 4:
        raise ValueError("PRONTO: too few words")
    if words[0] != 0x0000:
        raise ValueError("PRONTO: only learned format 0000 supported")

    freq_word = int(words[1]) & 0xFFFF

    # Take all timings after the preamble; ignore intro/repeat split/counts
    timings_units = words[4:]
    if len(timings_units) % 2 == 1:
        # If odd, drop last value (must be pairs)
        timings_units = timings_units[:-1]

    unit_us = freq_word * 0.241246

    # Convert each timing to microseconds (rounded half up, min 1 µs)
    pulses_us = [max(1, _round_half_up(u * unit_us)) for u in timings_units]

    # Convert microseconds to BroadLink ticks (floor)
    ticks = [int((us * BRDLNK_UNIT) // 1) for us in pulses_us]

    # Encode payload bytes
    payload = bytearray()
    for t in ticks:
        if t < 256:
            payload.append(t & 0xFF)
        else:
            payload.extend((0x00, (t >> 8) & 0xFF, t & 0xFF))

    # Build packet
    header = bytes((0x26, 0x00))
    length_le = bytes((len(payload) & 0xFF, (len(payload) >> 8) & 0xFF))
    tail = bytes((0x0D, 0x05))
    packet = bytearray(header + length_le + payload + tail)

    # Pad to multiple of 16 bytes (AES requirement)
    while len(packet) % 16 != 0:
        packet.append(0x00)

    int_list = list(packet)
    return bytes(packet)


# ---------------------------------------------------------------------------
# Pulses (µs) → BroadLink payload bytes
# ---------------------------------------------------------------------------


def pulses_to_broadlink_data(pulses_us: List[int]) -> bytes:
    """
    Encode microsecond pulses to BroadLink IR payload bytes:

      - ticks = floor(us * 269 / 8192); ticks may be 0
      - if ticks < 256 → one byte
      - else → 0x00 + two-byte big-endian ticks
      - packet = [0x26, 0x00] + [len LE 2 bytes] + [encoded pulses] + [0x0D, 0x05]
      - pad to multiple of 16 bytes with zeros
    """
    payload: bytearray = bytearray()
    for us in pulses_us:
        if us < 0:
            raise ValueError("Negative pulse not allowed")
        t = int((us * BRDLNK_UNIT) // 1)  # floor
        if t < 256:
            payload.append(t & 0xFF)
        else:
            payload.extend((0x00, (t >> 8) & 0xFF, t & 0xFF))

    header = bytes((0x26, 0x00))
    length_le = bytes((len(payload) & 0xFF, (len(payload) >> 8) & 0xFF))
    tail = bytes((0x0D, 0x05))
    packet = bytearray(header + length_le + payload + tail)

    # Pad to multiple of 16 bytes (AES requirement)
    while len(packet) % 16 != 0:
        packet.append(0x00)

    return bytes(packet)


# ---------------------------------------------------------------------------
# Normalization dispatcher for non-PRONTO formats
# ---------------------------------------------------------------------------


def _normalize_non_pronto(data: Union[str, List[int]]) -> List[int]:
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        t = data.strip()
        if t.lower().startswith("sendir"):
            return gc_to_pulses(t)
        if t.lower().startswith("3;"):
            return nec_to_pulses(t)
        raise ValueError(
            "Unrecognized IR format string (expected sendir/NEC/list for non-PRONTO)"
        )
    raise TypeError("Unsupported data type")


# ---------------------------------------------------------------------------
# Main public conversion APIs
# ---------------------------------------------------------------------------


def convert_to_broadlink(code: Union[str, List[int]]) -> bytes:
    """
    Convert any supported IR representation to a BroadLink raw packet (bytes).

    Accepts:
      - BroadLink raw HEX (starts with '26') → passthrough decode
      - PRONTO 0000 → encode to BroadLink
      - Global Caché sendir → encode to BroadLink
      - NEC custom → encode to BroadLink
      - list[int] pulses (µs) → encode to BroadLink
    """
    if isinstance(code, str):
        stripped = code.strip()
        # Raw BroadLink passthrough
        if _looks_like_broadlink_hex(stripped):
            return hex_to_broadlink(stripped)
        # PRONTO 0000
        if stripped.startswith("0000"):
            return pronto_to_broadlink(stripped)
        # Other recognized text formats → pulses
        pulses = _normalize_non_pronto(stripped)
        return pulses_to_broadlink_data(pulses)

    # Already a list of pulses
    if isinstance(code, list):
        return pulses_to_broadlink_data(code)

    raise TypeError("Unsupported code type")
