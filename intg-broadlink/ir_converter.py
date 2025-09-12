"""
Unified IR code conversion utilities for Broadlink devices.

Supported input formats:
- PRONTO 0000 (enhanced parsing: intro/repeat frames, hold simulation, trailing silence)
- Global Caché 'sendir' strings
- Custom NEC format: "3;0x<hex>;bits;repeat_count"
- Raw list[int] pulses in microseconds (already normalized)
- BroadLink raw HEX payload (starts with 0x26...) passthrough

Public main entry point for BroadLink packet creation:
    convert_to_broadlink(code)

Convenience helpers:
    pronto_to_broadlink(pronto_hex, ...)
    hex_to_broadlink(hex_string)
"""

from __future__ import annotations

from typing import List, Union
import binascii
import re

from broadlink.remote import pulses_to_data


# ---------------------------------------------------------------------------
# Global defaults
# ---------------------------------------------------------------------------

DEFAULT_HOLD_MS = 300  # approximate "tap" hold duration
DEFAULT_TRAILING_SILENCE_US = 105_000  # ~105 ms end gap
MAX_REPEAT_EXPANSIONS = 8
_SMALL_OFF_GAP_US = 560


# ---------------------------------------------------------------------------
# Utility: BroadLink raw HEX passthrough
# ---------------------------------------------------------------------------


def _clean_hex(s: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", s)


def _looks_like_broadlink_hex(s: str) -> bool:
    stripped = re.sub(r"\s+", "", s)
    if len(stripped) < 4 or len(stripped) % 2 != 0:
        return False
    if not re.fullmatch(r"[0-9A-Fa-f]+", stripped):
        return False
    return stripped.lower().startswith("26")


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
# PRONTO advanced unified path
# ---------------------------------------------------------------------------


def _parse_pronto_words(pronto_hex: str) -> List[int]:
    """
    Tolerant PRONTO parsing:
      - Removes all non-hex chars.
      - Requires total length multiple of 4.
    """
    cleaned = _clean_hex(pronto_hex)
    if len(cleaned) == 0 or len(cleaned) % 4 != 0:
        raise ValueError("PRONTO: hex length must be positive and multiple of 4")
    return [int(cleaned[i : i + 4], 16) for i in range(0, len(cleaned), 4)]


def _split_pronto(words: List[int]):
    """
    Split into (freq_word, intro_units, repeat_units) in PRONTO timing units.

    Forgiving logic:
      - Drops a dangling half pair.
      - If declared total pairs == 0 -> treat entire body as repeat_units.
      - If not enough timings -> allocate to intro first, remainder to repeat.
      - If excess timings -> trim.
    """
    if len(words) < 4:
        raise ValueError("PRONTO: too few words")
    if words[0] != 0x0000:
        raise ValueError("PRONTO: only 0000 format supported")

    freq_word = words[1]
    one_pairs = words[2]
    rep_pairs = words[3]

    timings = words[4:]
    if len(timings) % 2 == 1:
        timings = timings[:-1]

    declared_pairs = one_pairs + rep_pairs
    available_pairs = len(timings) // 2
    if available_pairs == 0:
        raise ValueError("PRONTO: no timing values")

    if declared_pairs == 0:
        return freq_word, [], timings

    if available_pairs >= declared_pairs:
        intro_units = timings[: one_pairs * 2]
        repeat_units = timings[one_pairs * 2 : one_pairs * 2 + rep_pairs * 2]
    else:
        intro_units_len = min(one_pairs * 2, len(timings))
        intro_units = timings[:intro_units_len]
        repeat_units = timings[intro_units_len:]

    return freq_word, intro_units, repeat_units


def pronto_to_pulses(
    pronto_hex: str,
    *,
    hold_ms: int = DEFAULT_HOLD_MS,
    trailing_silence_us: int = DEFAULT_TRAILING_SILENCE_US,
    repeat_cap: int = MAX_REPEAT_EXPANSIONS,
    repeat: bool = True,
    ensure_even: bool = True,
    add_trailing_silence: bool = True,
) -> List[int]:
    """
    Convert PRONTO 0000 code to microsecond pulses with:
      - Intro/repeat frame separation.
      - Repeat frame expansion to approximate a short press (if repeat units exist and repeat=True).
      - Even pulse normalization (optional).
      - Trailing silence appended (optional).

    Parameters:
        hold_ms: Approximate total active duration target for repeat block(s).
                 If 0, only one repeat frame is used.
        trailing_silence_us: Large final OFF gap (ignored if add_trailing_silence=False).
        repeat: Enable repeat-frame expansion if repeat section exists.
        repeat_cap: Max expansions (safety).
        ensure_even: Ensure pulses list length is even (add small OFF if needed).
        add_trailing_silence: Append trailing silence gap.

    Returns:
        List[int] microsecond pulses starting with ON.
    """
    words = _parse_pronto_words(pronto_hex)
    freq_word, intro_units, repeat_units = _split_pronto(words)
    if freq_word <= 0:
        raise ValueError("PRONTO: invalid frequency word")

    unit_us = freq_word * 0.241246

    def units_to_us(seq):
        return [max(1, int(round(u * unit_us))) for u in seq]

    pulses: List[int] = []

    if intro_units:
        pulses.extend(units_to_us(intro_units))

    if repeat_units:
        rep_us = units_to_us(repeat_units)
        reps = 1
        if repeat and hold_ms > 0:
            target_us = hold_ms * 1000
            period = sum(rep_us) or 1
            if target_us > period:
                reps = (target_us + period - 1) // period
            reps = min(max(reps, 1), max(1, repeat_cap))
        for _ in range(reps):
            pulses.extend(rep_us)
    elif not intro_units:
        # Entire body fallback (declared counts zero or absent)
        body = words[4:]
        if len(body) % 2 == 1:
            body = body[:-1]
        pulses.extend(units_to_us(body))

    if ensure_even and (len(pulses) % 2 == 1):
        pulses.append(_SMALL_OFF_GAP_US)

    if add_trailing_silence and trailing_silence_us > 0:
        pulses.append(trailing_silence_us)

    return pulses


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


def convert_to_broadlink(
    code: Union[str, List[int]],
    **pronto_kwargs,
) -> bytes:
    """
    Convert any supported IR representation to a BroadLink raw packet (bytes).

    Accepts:
      - PRONTO 0000 (auto-detected)
      - Global Caché sendir
      - NEC custom
      - list[int] pulses (µs)
      - BroadLink raw HEX (starts with '26')

    Additional keyword args are passed directly to `pronto_to_pulses` for PRONTO input
    (e.g., hold_ms=0 to disable expansion, add_trailing_silence=False to skip trailing gap).

    Examples:
        convert_to_broadlink(pronto_code)  # default advanced behavior
        convert_to_broadlink(pronto_code, hold_ms=0, repeat=False, add_trailing_silence=False)
        convert_to_broadlink(gcsendir_code)
        convert_to_broadlink(nec_code_str)
        convert_to_broadlink([9000,4500,560,560, ...])  # pulses list
        convert_to_broadlink("2600...")  # raw BroadLink HEX
    """
    if isinstance(code, str):
        stripped = code.strip()
        # Raw BroadLink passthrough
        if _looks_like_broadlink_hex(stripped):
            return hex_to_broadlink(stripped)
        # PRONTO
        if stripped.startswith("0000"):
            pulses = pronto_to_pulses(stripped, **pronto_kwargs)
            return pulses_to_data(pulses)
        # Other recognized text formats
        pulses = _normalize_non_pronto(stripped)
        return pulses_to_data(pulses)

    # Already a list of pulses
    if isinstance(code, list):
        return pulses_to_data(code)

    raise TypeError("Unsupported code type")


def pronto_to_broadlink(
    pronto_hex: str,
    **kwargs,
) -> bytes:
    """
    Convenience wrapper: PRONTO → BroadLink bytes.
    Keyword args forwarded to pronto_to_pulses.
    """
    pulses = pronto_to_pulses(pronto_hex, **kwargs)
    return pulses_to_data(pulses)
