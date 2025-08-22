"""
IR code conversion utilities for Broadlink devices.

This module provides functions to convert HEX and PRONTO IR codes
into the Broadlink IR raw format.
"""

import logging
import struct

_LOG = logging.getLogger(__name__)

# Broadlink timing constants
BROADLINK_TICK = 32.84  # microseconds per tick
IR_COMMAND_TYPE = 0x26  # Command type for IR


def custom_to_broadlink(custom_code: str) -> bytes:
    """
    Convert custom semicolon-separated IR code to Broadlink format.

    Supports format: protocol;hex_value;bits;repeat
    Currently supports NEC protocol (protocol=3).

    Args:
        custom_code: Custom format IR code (e.g., "3;0x1FE50AF;32;0")

    Returns:
        bytes: Broadlink format IR code

    Raises:
        ValueError: If custom_code is invalid or unsupported protocol
    """
    if not custom_code:
        raise ValueError("Custom code cannot be empty")

    try:
        parts = custom_code.split(";")
        if len(parts) != 4:
            raise ValueError(
                "Custom code must have format: protocol;hex_value;bits;repeat"
            )

        protocol = int(parts[0])
        hex_value = (
            int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1], 16)
        )
        bits = int(parts[2])
        repeat = int(parts[3])

    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid custom code format: {e}") from e

    if protocol == 3:  # NEC protocol
        return _nec_to_broadlink(hex_value, bits, repeat)
    else:
        raise ValueError(f"Unsupported protocol: {protocol}")


def _nec_to_broadlink(nec_value: int, bits: int = 32, repeat: int = 0) -> bytes:
    """
    Convert NEC protocol value to Broadlink format.
    Converts a 32-bit NEC protocol value into PRONTO format for Broadlink IR devices.
    Args:
        nec_value: NEC protocol 32-bit value
        bits: Number of bits (should be 32 for standard NEC)
        repeat: Repeat count (not used in current implementation)

    Returns:
        str: PRONTO format IR code
    """
    if bits != 32:
        raise ValueError("NEC protocol requires 32 bits")

    # Validate NEC format (address + ~address + command + ~command)
    command = nec_value & 0xFF
    command_inv = (nec_value >> 8) & 0xFF
    address = (nec_value >> 16) & 0xFF
    address_inv = (nec_value >> 24) & 0xFF

    # Check if it's valid NEC (inverse bytes should sum to 255)
    if (address + address_inv) != 255 or (command + command_inv) != 255:
        _LOG.warning(
            "NEC validation failed: addr=0x%02X+0x%02X=%d, cmd=0x%02X+0x%02X=%d",
            address,
            address_inv,
            address + address_inv,
            command,
            command_inv,
            command + command_inv,
        )

    # PRONTO frequency code for 38kHz
    freq_code = 0x006C

    # NEC timing in PRONTO units (26.3 μs per unit)
    time_base = 26.3  # microseconds per PRONTO unit

    def us_to_pronto(microseconds):
        return int(round(microseconds / time_base))

    # NEC protocol timings
    leading_on = us_to_pronto(9000)  # 9ms leading pulse
    leading_off = us_to_pronto(4500)  # 4.5ms leading space
    bit_on = us_to_pronto(562)  # 0.562ms bit pulse
    bit0_off = us_to_pronto(562)  # 0.562ms for '0' bit
    bit1_off = us_to_pronto(1687)  # 1.687ms for '1' bit
    stop_on = us_to_pronto(562)  # 0.562ms stop pulse

    # Build pulse sequence
    pulses = []

    # Leading burst
    pulses.extend([leading_on, leading_off])

    # Data bits (LSB first for NEC)
    for i in range(32):
        bit = (nec_value >> i) & 1
        pulses.append(bit_on)
        if bit:
            pulses.append(bit1_off)  # '1' bit
        else:
            pulses.append(bit0_off)  # '0' bit

    # Stop bit
    pulses.append(stop_on)

    # Build PRONTO code
    seq1_length = len(pulses)
    seq2_length = 0

    # Format as PRONTO hex string
    pronto_parts = [
        "0000",  # Raw/learned code format
        f"{freq_code:04X}",  # Frequency code
        f"{seq1_length:04X}",  # Sequence 1 length
        f"{seq2_length:04X}",  # Sequence 2 length
    ]

    # Add pulse data
    for pulse in pulses:
        pronto_parts.append(f"{pulse:04X}")

    pronto = " ".join(pronto_parts)
    return pronto_to_broadlink(pronto)


def hex_to_broadlink(hex_code: str) -> bytes:
    """
    Convert HEX IR code to Broadlink IR raw format.

    Args:
        hex_code: Hexadecimal string representing IR pulse data

    Returns:
        bytes: Broadlink IR raw format data

    Raises:
        ValueError: If hex_code is invalid or empty
    """
    if not hex_code:
        raise ValueError("HEX code cannot be empty")

    # Remove any whitespace and ensure even length
    hex_code = hex_code.replace(" ", "").replace("\n", "").replace("\t", "")
    if len(hex_code) % 2 != 0:
        raise ValueError("HEX code must have even number of characters")

    try:
        # Convert hex string to bytes
        raw_data = bytes.fromhex(hex_code)
    except ValueError as e:
        raise ValueError(f"Invalid HEX code format: {e}") from e

    # Create Broadlink packet
    return _create_broadlink_packet(raw_data)


def pronto_to_broadlink(pronto_code: str) -> bytes:
    """
    Convert PRONTO IR code to Broadlink IR raw format.

    Args:
        pronto_code: PRONTO format IR code string

    Returns:
        bytes: Broadlink IR raw format data

    Raises:
        ValueError: If pronto_code is invalid or empty
    """
    if not pronto_code:
        raise ValueError("PRONTO code cannot be empty")

    # Parse PRONTO code
    try:
        pronto_data = [int(x, 16) for x in pronto_code.split()]
    except ValueError as e:
        raise ValueError(f"Invalid PRONTO code format: {e}") from e

    if len(pronto_data) < 4:
        raise ValueError("PRONTO code too short, minimum 4 values required")

    # Extract PRONTO header
    frequency_code = pronto_data[1]
    seq1_length = pronto_data[2]
    seq2_length = pronto_data[3]

    # Extract pulse data
    pulse_data = pronto_data[4:]
    expected_length = seq1_length + seq2_length

    if len(pulse_data) < expected_length:
        raise ValueError(
            f"PRONTO code data too short, expected {expected_length} values"
        )

    # Convert PRONTO timings to Broadlink format
    broadlink_data = _pronto_to_broadlink_pulses(
        pulse_data[:expected_length], frequency_code
    )

    return _create_broadlink_packet(broadlink_data)


def _pronto_to_broadlink_pulses(pronto_pulses: list, frequency_code: int) -> bytes:
    """
    Convert PRONTO pulse timings to Broadlink pulse format.

    Args:
        pronto_pulses: List of PRONTO timing values
        frequency_code: PRONTO frequency code

    Returns:
        bytes: Broadlink pulse data
    """
    # Calculate timing conversion factor
    if frequency_code == 0:
        # Learned codes use 1/36000 second units
        time_base = 1000000 / 36000  # microseconds
    else:
        # Generated codes use frequency-based timing
        time_base = 1000000 / (frequency_code * 0.241246)

    broadlink_pulses = []

    for pulse in pronto_pulses:
        if pulse == 0:
            continue

        # Convert to microseconds then to Broadlink ticks
        duration_us = pulse * time_base
        broadlink_ticks = int(duration_us / BROADLINK_TICK)

        # Clamp to maximum value to prevent overflow
        if broadlink_ticks > 65535:
            broadlink_ticks = 65535

        # Encode duration according to Broadlink format
        if broadlink_ticks <= 255:
            broadlink_pulses.append(broadlink_ticks)
        else:
            # Long duration: 0x00 followed by 16-bit big-endian value
            broadlink_pulses.append(0x00)
            broadlink_pulses.extend(struct.pack(">H", broadlink_ticks))

    return bytes(broadlink_pulses)


def _create_broadlink_packet(pulse_data: bytes) -> bytes:
    """
    Create a complete Broadlink IR packet with headers.

    Args:
        pulse_data: Raw pulse timing data

    Returns:
        bytes: Complete Broadlink IR packet
    """
    # Create packet header
    header = bytearray()
    header.append(IR_COMMAND_TYPE)  # Command type (0x26 for IR)
    header.append(0x00)  # Command repeat (0x00 for no repeat)

    # Add payload length (little-endian 16-bit)
    payload_length = len(pulse_data)
    header.extend(struct.pack("<H", payload_length))

    # Combine header and pulse data
    packet = header + pulse_data

    # Pad to multiple of 16 bytes for AES encryption
    padding_needed = (16 - (len(packet) % 16)) % 16
    if padding_needed:
        packet.extend(b"\x00" * padding_needed)

    return bytes(packet)


def validate_broadlink_packet(packet: bytes) -> bool:
    """
    Validate a Broadlink IR packet format.

    Args:
        packet: Broadlink IR packet to validate

    Returns:
        bool: True if packet format is valid
    """
    if len(packet) < 4:
        return False

    # Check command type
    if packet[0] != IR_COMMAND_TYPE:
        return False

    # Check packet length is multiple of 16
    if len(packet) % 16 != 0:
        return False

    # Extract and verify payload length
    payload_length = struct.unpack("<H", packet[2:4])[0]
    expected_total_length = 4 + payload_length

    # Account for padding
    if expected_total_length % 16 != 0:
        expected_total_length += 16 - (expected_total_length % 16)

    return len(packet) == expected_total_length
