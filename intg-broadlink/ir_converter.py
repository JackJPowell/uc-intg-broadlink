"""
IR code conversion utilities for Broadlink devices.

This module provides functions to convert HEX and PRONTO IR codes
into the Broadlink IR raw format.
"""

from broadlink.remote import pulses_to_data

from typing import List, Union, Tuple, Optional, Literal


def hex_to_words(pronto_hex: str) -> List[int]:
    """Convert a PRONTO hex string into a list of integers (words)."""
    pronto_hex = pronto_hex.strip().replace(" ", "").replace("\n", "")
    if len(pronto_hex) % 4 != 0:
        raise ValueError("Invalid PRONTO hex length")
    return [int(pronto_hex[i : i + 4], 16) for i in range(0, len(pronto_hex), 4)]


def pronto_to_pulses(pronto: str) -> List[int]:
    """Convert Pronto hex string into pulse lengths in microseconds."""
    codes = [int(x, 16) for x in pronto.strip().split()]
    if codes[0] != 0x0000:
        raise ValueError("Only raw Pronto format supported")

    freq_word = codes[1]
    if freq_word <= 0:
        raise ValueError("Invalid Pronto frequency word")

    # Each duration unit = carrier period (µs) = 0.241246 * freq_word
    unit_us = 0.241246 * freq_word

    sequence = codes[4:]
    return [int(round(x * unit_us)) for x in sequence]


def gc_to_pulses(gc_str: str) -> List[int]:
    """
    Convert Global Caché 'sendir' string into microsecond pulses.
    Example: "sendir,1:1,1,38000,1,1,343,171,21,21..."
    """
    parts = gc_str.strip().split(",")
    if not parts[0].lower().startswith("sendir"):
        raise ValueError("Not a Global Caché sendir string")

    # frequency in Hz
    freq = int(parts[3])
    # convert carrier cycles to µs: each unit = 1/freq seconds
    unit_micros = 1_000_000 / freq

    # pulse list starts at index 6
    pulse_counts = list(map(int, parts[6:]))
    return [round(c * unit_micros) for c in pulse_counts]


def nec_to_pulses(code_str, lsb_first=False):
    """
    Convert custom NEC IR code format to pulse data.

    Format: <protocol>;<hex-ir-code>;<bits>;<repeat-count>
    Example: "3;0x1FE50AF;32;0"
    """
    try:
        proto, hex_code, nbits, repeat = code_str.split(";")
        proto = int(proto)
        if proto != 3:
            raise ValueError("Only NEC (protocol=3) supported right now.")

        code = int(hex_code, 16)
        nbits = int(nbits)
        repeat = int(repeat)

    except Exception as e:
        raise ValueError(f"Invalid code string '{code_str}': {e}")

    # NEC timing constants
    tick = 560
    header_mark = 16 * tick  # 9000
    header_space = 8 * tick  # 4500
    one_space = 3 * tick  # 1680
    zero_space = 1 * tick  # 560

    pulses = []
    pulses += [header_mark, header_space]

    for i in range(nbits):
        if lsb_first:
            bit = (code >> i) & 1  # LSB first
        else:
            bit = (code >> (nbits - 1 - i)) & 1  # MSB first

        pulses.append(tick)  # mark
        pulses.append(one_space if bit else zero_space)

    # final mark
    pulses.append(tick)

    # trailing gap: NEC frame ~108ms
    frame_len = 108000
    gap = frame_len - sum(pulses)
    if gap > 0:
        pulses.append(gap)

    # add repeats if needed
    full = pulses[:]
    for _ in range(repeat):
        # NEC repeat frame: 9ms mark + 2.25ms space + 560us mark + gap
        rep = [16 * tick, 4 * tick, tick]
        rep_gap = frame_len - sum(rep)
        if rep_gap > 0:
            rep.append(rep_gap)
        full += rep

    return full


def normalize_ir(data: Union[str, List[int]]) -> List[int]:
    """
    Normalize IR data to a list of microsecond pulses.
    - If list[int] is passed, assumes already µs pulses.
    - If PRONTO hex string is passed, parses and converts.
    - If Global Caché 'sendir' is passed, parses and converts.
    """
    if isinstance(data, list):
        # Already µs pulses
        return data
    elif isinstance(data, str):
        text = data.strip()
        if text.startswith("0000"):  # PRONTO
            return pronto_to_pulses(text)
        elif text.lower().startswith("sendir"):  # Global Caché
            return gc_to_pulses(text)
        elif text.lower().startswith("3;"):  # NEC format e.g. "3;0x20DF10EF;32;0"
            return nec_to_pulses(text)
        else:
            raise ValueError("Unrecognized IR format string")
    else:
        raise TypeError("Unsupported data type")


def split_custom_format(data: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Split a custom IR format string into its components.
    """
    parts = data.split(";")
    if len(parts) == 4:
        return parts


def convert_to_broadlink(code: str) -> str:
    """
    Convert an IR code string into Broadlink format.
    """
    pulses = normalize_ir(code)
    broadlink_data = pulses_to_data(pulses)
    return broadlink_data
