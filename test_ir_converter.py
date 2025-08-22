#!/usr/bin/env python3
"""
Test suite for the IR converter module.

This module tests all IR converter functions with various inputs
to ensure correct conversion and error handling.
"""

import sys
import unittest
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
    IR_COMMAND_TYPE,
)


class TestHexToBroadlink(unittest.TestCase):
    """Test cases for hex_to_broadlink function."""

    def test_valid_hex_conversion(self):
        """Test conversion of valid HEX codes."""
        # Test with a simple HEX code
        hex_code = (
            "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05"
        )
        result = hex_to_broadlink(hex_code)

        # Check that result is bytes
        self.assertIsInstance(result, bytes)

        # Check that packet is valid
        self.assertTrue(validate_broadlink_packet(result))

        # Check header structure
        self.assertEqual(result[0], IR_COMMAND_TYPE)  # Command type
        self.assertEqual(result[1], 0x00)  # Command repeat

        # Check that length is multiple of 16 (for AES encryption)
        self.assertEqual(len(result) % 16, 0)

    def test_empty_hex_code(self):
        """Test that empty HEX code raises ValueError."""
        with self.assertRaises(ValueError) as context:
            hex_to_broadlink("")
        self.assertIn("cannot be empty", str(context.exception))

    def test_odd_length_hex_code(self):
        """Test that odd-length HEX code raises ValueError."""
        with self.assertRaises(ValueError) as context:
            hex_to_broadlink("ABC")
        self.assertIn("even number of characters", str(context.exception))

    def test_invalid_hex_characters(self):
        """Test that invalid hex characters raise ValueError."""
        with self.assertRaises(ValueError) as context:
            hex_to_broadlink("XYZW")
        self.assertIn("Invalid HEX code format", str(context.exception))

    def test_hex_with_whitespace(self):
        """Test that whitespace is properly removed."""
        hex_code = "26 00 1A 00"
        result = hex_to_broadlink(hex_code)
        self.assertIsInstance(result, bytes)
        self.assertTrue(validate_broadlink_packet(result))


class TestProntoToBroadlink(unittest.TestCase):
    """Test cases for pronto_to_broadlink function."""

    def test_valid_pronto_conversion(self):
        """Test conversion of valid PRONTO codes."""
        pronto_code = (
            "0000 006C 0022 0002 015B 00AD 0016 0041 0016 0041 "
            "0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 "
            "0016 0041 0016 0041 0016 0041 0016 0016 0016 0016 "
            "0016 0016 0016 0016 0016 0041 0016 0016 0016 0041 "
            "0016 0016 0016 0016 0016 0016 0016 0016 0016 0016 "
            "0016 0016 0016 0041 0016 0016 0016 0041 0016 0041 "
            "0016 0041 0016 0041 0016 0041 0016 0041 0016 06A4"
        )

        result = pronto_to_broadlink(pronto_code)

        # Check that result is bytes
        self.assertIsInstance(result, bytes)

        # Check that packet is valid
        self.assertTrue(validate_broadlink_packet(result))

        # Check header structure
        self.assertEqual(result[0], IR_COMMAND_TYPE)
        self.assertEqual(result[1], 0x00)

    def test_empty_pronto_code(self):
        """Test that empty PRONTO code raises ValueError."""
        with self.assertRaises(ValueError) as context:
            pronto_to_broadlink("")
        self.assertIn("cannot be empty", str(context.exception))

    def test_short_pronto_code(self):
        """Test that too-short PRONTO code raises ValueError."""
        with self.assertRaises(ValueError) as context:
            pronto_to_broadlink("0000 006C")
        self.assertIn("too short", str(context.exception))

    def test_invalid_pronto_format(self):
        """Test that invalid PRONTO format raises ValueError."""
        with self.assertRaises(ValueError) as context:
            pronto_to_broadlink("invalid format")
        self.assertIn("Invalid PRONTO code format", str(context.exception))

    def test_insufficient_pulse_data(self):
        """Test that insufficient pulse data raises ValueError."""
        with self.assertRaises(ValueError) as context:
            pronto_to_broadlink(
                "0000 006C 0010 0002 015B"
            )  # Claims 16 pulses but only has 1
        self.assertIn("too short", str(context.exception))


class TestCustomToBroadlink(unittest.TestCase):
    """Test cases for custom_to_broadlink function."""

    def test_valid_nec_conversion(self):
        """Test conversion of valid NEC codes."""
        nec_code = "3;0x1FE50AF;32;0"
        result = custom_to_broadlink(nec_code)

        # Check that result is bytes
        self.assertIsInstance(result, bytes)

        # Check that packet is valid
        self.assertTrue(validate_broadlink_packet(result))

    def test_nec_without_0x_prefix(self):
        """Test NEC codes without 0x prefix."""
        nec_code = "3;1FE50AF;32;0"
        result = custom_to_broadlink(nec_code)
        self.assertIsInstance(result, bytes)
        self.assertTrue(validate_broadlink_packet(result))

    def test_empty_custom_code(self):
        """Test that empty custom code raises ValueError."""
        with self.assertRaises(ValueError) as context:
            custom_to_broadlink("")
        self.assertIn("cannot be empty", str(context.exception))

    def test_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with self.assertRaises(ValueError) as context:
            custom_to_broadlink("invalid;format")
        self.assertIn("Custom code must have format", str(context.exception))

    def test_unsupported_protocol(self):
        """Test that unsupported protocol raises ValueError."""
        with self.assertRaises(ValueError) as context:
            custom_to_broadlink("1;0x1FE50AF;32;0")  # Protocol 1 is not supported
        self.assertIn("Unsupported protocol", str(context.exception))

    def test_invalid_hex_value(self):
        """Test that invalid hex value raises ValueError."""
        with self.assertRaises(ValueError) as context:
            custom_to_broadlink("3;invalid_hex;32;0")
        self.assertIn("Invalid custom code format", str(context.exception))

    def test_invalid_bits_value(self):
        """Test that invalid bits value raises ValueError."""
        with self.assertRaises(ValueError) as context:
            custom_to_broadlink("3;0x1FE50AF;invalid;0")
        self.assertIn("Invalid custom code format", str(context.exception))


class TestValidateBroadlinkPacket(unittest.TestCase):
    """Test cases for validate_broadlink_packet function."""

    def test_valid_packet(self):
        """Test that valid packets are recognized."""
        # Create a valid packet using hex_to_broadlink
        hex_code = "26001A00"
        packet = hex_to_broadlink(hex_code)
        self.assertTrue(validate_broadlink_packet(packet))

    def test_short_packet(self):
        """Test that packets too short are invalid."""
        packet = b"\x26\x00"  # Only 2 bytes
        self.assertFalse(validate_broadlink_packet(packet))

    def test_wrong_command_type(self):
        """Test that packets with wrong command type are invalid."""
        packet = b"\x25\x00\x04\x00" + b"\x00" * 12  # Wrong command type
        self.assertFalse(validate_broadlink_packet(packet))

    def test_wrong_length(self):
        """Test that packets not multiple of 16 are invalid."""
        packet = b"\x26\x00\x04\x00\x00\x00\x00\x00"  # 8 bytes, not multiple of 16
        self.assertFalse(validate_broadlink_packet(packet))


class TestIntegration(unittest.TestCase):
    """Integration tests for the IR converter module."""

    def test_round_trip_consistency(self):
        """Test that different inputs produce valid packets."""
        test_cases = [
            ("hex", "26001A00AC005D00"),
            ("pronto", "0000 006C 0004 0000 015B 00AD 0016 0041"),
            ("custom", "3;0x1FE50AF;32;0"),
        ]

        for code_type, code in test_cases:
            with self.subTest(code_type=code_type):
                if code_type == "hex":
                    result = hex_to_broadlink(code)
                elif code_type == "pronto":
                    result = pronto_to_broadlink(code)
                elif code_type == "custom":
                    result = custom_to_broadlink(code)

                # All should produce valid packets
                self.assertTrue(validate_broadlink_packet(result))

                # All should be encodable to base64
                b64_code = base64.b64encode(result).decode()
                self.assertTrue(len(b64_code) > 0)

    def test_base64_encoding(self):
        """Test that all conversion results can be base64 encoded."""
        hex_code = "26001A00"
        result = hex_to_broadlink(hex_code)

        # Should be able to encode to base64
        b64_code = base64.b64encode(result).decode()
        self.assertTrue(len(b64_code) > 0)

        # Should be able to decode back
        decoded = base64.b64decode(b64_code)
        self.assertEqual(result, decoded)


def run_tests():
    """Run all tests and display results."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
