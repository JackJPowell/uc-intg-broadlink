#!/usr/bin/env python3
"""
Example usage of the IR converter module.

This script demonstrates how to convert HEX and PRONTO IR codes
to Broadlink format using the ir_converter module.
"""

import sys
import base64
from pathlib import Path

# Add the intg-broadlink directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "intg-broadlink"))

# Import IR converter functions after path modification
# flake8: noqa: E402
from ir_converter import (
    hex_to_broadlink,
    pronto_to_broadlink,
    custom_to_broadlink,
    validate_broadlink_packet,
)


def main():
    """Run example conversions."""
    print("IR Code Converter Examples")
    print("=" * 50)

    # Example 1: HEX to Broadlink conversion
    print("\n1. HEX to Broadlink conversion:")
    hex_code = "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05"
    print(f"HEX Code: {hex_code}")

    try:
        broadlink_data = hex_to_broadlink(hex_code)
        b64_code = base64.b64encode(broadlink_data).decode()
        print(f"Broadlink (Base64): {b64_code}")
        print(f"Packet valid: {validate_broadlink_packet(broadlink_data)}")
        print(f"Packet length: {len(broadlink_data)} bytes")
    except ValueError as e:
        print(f"Error: {e}")

    # Example 2: PRONTO to Broadlink conversion
    print("\n2. PRONTO to Broadlink conversion:")
    pronto_code = (
        "0000 006C 0022 0002 015B 00AD 0016 0041 0016 0041 0016 0041 "
        "0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 0016 0041 "
        "0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 "
        "0016 0016 0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 "
        "0016 0016 0016 0016 0016 0041 0016 0016 0016 0041 0016 0041 "
        "0016 0041 0016 0041 0016 0041 0016 0041 0016 06A4"
    )
    print(f"PRONTO Code: {pronto_code[:50]}...")

    try:
        broadlink_data = pronto_to_broadlink(pronto_code)
        b64_code = base64.b64encode(broadlink_data).decode()
        print(f"Broadlink (Base64): {b64_code}")
        print(f"Packet valid: {validate_broadlink_packet(broadlink_data)}")
        print(f"Packet length: {len(broadlink_data)} bytes")
    except ValueError as e:
        print(f"Error: {e}")

    # Example 3: Custom NEC format to Broadlink conversion
    print("\n3. Custom NEC format to Broadlink conversion:")
    nec_code = "3;0x1FE50AF;32;0"
    print(f"NEC Code: {nec_code}")

    try:
        broadlink_data = custom_to_broadlink(nec_code)
        b64_code = base64.b64encode(broadlink_data).decode()
        print(f"Broadlink (Base64): {b64_code}")
        print(f"Packet valid: {validate_broadlink_packet(broadlink_data)}")
        print(f"Packet length: {len(broadlink_data)} bytes")
    except ValueError as e:
        print(f"Error: {e}")

    # Example 4: Error handling demonstration
    print("\n4. Error handling examples:")

    # Invalid HEX code
    try:
        hex_to_broadlink("invalid_hex")
    except ValueError as e:
        print(f"Invalid HEX error: {e}")

    # Empty input
    try:
        pronto_to_broadlink("")
    except ValueError as e:
        print(f"Empty PRONTO error: {e}")

    # Invalid custom format
    try:
        custom_to_broadlink("invalid;format")
    except ValueError as e:
        print(f"Invalid custom format error: {e}")

    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    main()
