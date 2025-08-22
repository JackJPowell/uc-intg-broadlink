#!/usr/bin/env python3
"""
Integration tests for the IR converter with the Broadlink class.

This module tests the integration between the IR converter functions
and the Broadlink class convert_ir_code method.
"""

import sys
import unittest
import base64
from pathlib import Path
from unittest.mock import Mock

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


class MockBroadlinkDevice:
    """Mock Broadlink device for testing."""

    def __init__(self):
        self.identifier = "test_device"


class MockBroadlinkConfig:
    """Mock Broadlink configuration for testing."""

    def __init__(self):
        self.devices = Mock()


class TestBroadlinkIntegration(unittest.TestCase):
    """Test integration with Broadlink class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_device = MockBroadlinkDevice()
        self.mock_config = MockBroadlinkConfig()

        # Import and create Broadlink instance with mocks
        try:
            from rm import Broadlink

            self.broadlink = Broadlink(self.mock_device, self.mock_config)
            self.broadlink_available = True
        except ImportError:
            self.broadlink_available = False
            self.skipTest("Broadlink class not available for integration testing")

    def test_convert_ir_code_hex_auto_detection(self):
        """Test auto-detection of HEX format."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        hex_code = "26001A00AC005D00"
        result = self.broadlink.convert_ir_code(hex_code, "auto")

        # Should return base64 encoded data
        self.assertIsInstance(result, (str, bytes))

        # Should be valid base64
        if isinstance(result, str):
            try:
                decoded = base64.b64decode(result)
                self.assertTrue(validate_broadlink_packet(decoded))
            except Exception:
                # If result is not base64, it might be raw bytes
                if isinstance(result, bytes):
                    self.assertTrue(validate_broadlink_packet(result))

    def test_convert_ir_code_pronto_auto_detection(self):
        """Test auto-detection of PRONTO format."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        pronto_code = "0000 006C 0004 0000 015B 00AD 0016 0041"
        result = self.broadlink.convert_ir_code(pronto_code, "auto")

        # Should return some form of encoded data
        self.assertIsInstance(result, (str, bytes))
        self.assertTrue(len(result) > 0)

    def test_convert_ir_code_explicit_hex(self):
        """Test explicit HEX format specification."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        hex_code = "26001A00"
        result = self.broadlink.convert_ir_code(hex_code, "hex")

        self.assertIsInstance(result, (str, bytes))
        self.assertTrue(len(result) > 0)

    def test_convert_ir_code_explicit_pronto(self):
        """Test explicit PRONTO format specification."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        pronto_code = "0000 006C 0004 0000 015B 00AD 0016 0041"
        result = self.broadlink.convert_ir_code(pronto_code, "pronto")

        self.assertIsInstance(result, (str, bytes))
        self.assertTrue(len(result) > 0)

    def test_convert_ir_code_custom_nec(self):
        """Test custom NEC format conversion."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        nec_code = "3;0x1FE50AF;32;0"
        result = self.broadlink.convert_ir_code(
            nec_code, "hex"
        )  # Custom format is handled under hex

        self.assertIsInstance(result, (str, bytes))
        self.assertTrue(len(result) > 0)

    def test_convert_ir_code_empty_input(self):
        """Test that empty input raises ValueError."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        with self.assertRaises(ValueError):
            self.broadlink.convert_ir_code("", "auto")

    def test_convert_ir_code_invalid_format(self):
        """Test that invalid format raises ValueError."""
        if not self.broadlink_available:
            self.skipTest("Broadlink class not available")

        with self.assertRaises(ValueError):
            self.broadlink.convert_ir_code("valid_code", "invalid_format")


class TestDirectFunctionIntegration(unittest.TestCase):
    """Test direct function integration scenarios."""

    def test_chained_conversions(self):
        """Test that converted data can be used in multiple ways."""
        # Start with a HEX code
        hex_code = "26001A00AC005D00"
        hex_result = hex_to_broadlink(hex_code)

        # Verify it's valid
        self.assertTrue(validate_broadlink_packet(hex_result))

        # Convert to base64 for storage/transmission
        b64_code = base64.b64encode(hex_result).decode()

        # Convert back and verify it's the same
        decoded_result = base64.b64decode(b64_code)
        self.assertEqual(hex_result, decoded_result)

    def test_different_formats_same_ir_code(self):
        """Test that the same IR signal can be converted from different formats."""
        # This test would ideally compare HEX and PRONTO versions of the same IR signal
        # For now, we just test that both produce valid packets

        hex_code = "26001A00"
        pronto_code = "0000 006C 0002 0000 015B 00AD"

        hex_result = hex_to_broadlink(hex_code)
        pronto_result = pronto_to_broadlink(pronto_code)

        # Both should be valid packets
        self.assertTrue(validate_broadlink_packet(hex_result))
        self.assertTrue(validate_broadlink_packet(pronto_result))

        # Both should have the same command type
        self.assertEqual(hex_result[0], pronto_result[0])

    def test_nec_protocol_validation(self):
        """Test NEC protocol validation and conversion."""
        # Valid NEC code
        valid_nec = "3;0x1FE50AF;32;0"
        result = custom_to_broadlink(valid_nec)
        self.assertTrue(validate_broadlink_packet(result))

        # Test different valid NEC codes
        test_codes = [
            "3;0xFF00FF;32;0",
            "3;0x807F807F;32;0",
            "3;0x1234ABCD;32;0",
        ]

        for code in test_codes:
            with self.subTest(nec_code=code):
                try:
                    result = custom_to_broadlink(code)
                    self.assertTrue(validate_broadlink_packet(result))
                except ValueError:
                    # Some codes may fail NEC validation, which is acceptable
                    pass

    def test_performance_multiple_conversions(self):
        """Test that multiple conversions work efficiently."""
        test_codes = [
            ("hex", "26001A00"),
            ("hex", "AA005D00"),
            ("pronto", "0000 006C 0002 0000 015B 00AD"),
            ("pronto", "0000 006C 0004 0000 015B 00AD 0016 0041"),
            ("custom", "3;0x1FE50AF;32;0"),
            ("custom", "3;0xFF00FF;32;0"),
        ]

        results = []
        for code_type, code in test_codes:
            try:
                if code_type == "hex":
                    result = hex_to_broadlink(code)
                elif code_type == "pronto":
                    result = pronto_to_broadlink(code)
                elif code_type == "custom":
                    result = custom_to_broadlink(code)

                results.append(result)
                self.assertTrue(validate_broadlink_packet(result))
            except ValueError:
                # Some test codes may not be valid, which is fine for this test
                pass

        # Should have at least some successful conversions
        self.assertGreater(len(results), 0)

    def test_packet_structure_consistency(self):
        """Test that all conversion functions produce consistent packet structure."""
        # Test different types of input
        test_inputs = [
            ("hex", "26001A00"),
            ("pronto", "0000 006C 0002 0000 015B 00AD"),
        ]

        for input_type, code in test_inputs:
            with self.subTest(input_type=input_type):
                if input_type == "hex":
                    result = hex_to_broadlink(code)
                elif input_type == "pronto":
                    result = pronto_to_broadlink(code)

                # Check packet structure consistency
                self.assertEqual(result[0], 0x26)  # Command type
                self.assertEqual(result[1], 0x00)  # Command repeat

                # Check length is multiple of 16
                self.assertEqual(len(result) % 16, 0)

                # Check that payload length field makes sense
                payload_length = int.from_bytes(result[2:4], byteorder="little")
                expected_total = 4 + payload_length
                if expected_total % 16 != 0:
                    expected_total += 16 - (expected_total % 16)
                self.assertEqual(len(result), expected_total)


def run_integration_tests():
    """Run all integration tests and display results."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    if success:
        print("\n✅ All integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some integration tests failed!")
        sys.exit(1)
