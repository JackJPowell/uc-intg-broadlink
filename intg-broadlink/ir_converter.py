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
