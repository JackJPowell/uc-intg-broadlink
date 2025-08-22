#!/usr/bin/env python3
"""
Test script for the custom IR code converter functionality.
"""

import sys
from pathlib import Path

# Add the intg-broadlink directory to the path
sys.path.insert(0, str(Path(__file__).parent / "intg-broadlink"))

from ir_converter import custom_to_pronto, pronto_to_broadlink, nec_to_broadlink
import base64

def test_custom_to_pronto():
    """Test converting custom format to PRONTO."""
    print("Testing custom_to_pronto function...")
    
    # Test the exact case from the problem statement
    custom_code = "3;0x1FE50AF;32;0"
    
    try:
        pronto_code = custom_to_pronto(custom_code)
        print(f"✓ Successfully converted: {custom_code}")
        print(f"  PRONTO: {pronto_code[:50]}...")
        
        # Validate PRONTO format
        parts = pronto_code.split()
        assert parts[0] == "0000", "Invalid PRONTO format identifier"
        assert parts[1] == "006C", "Invalid frequency code"
        assert len(parts) >= 4, "PRONTO code too short"
        
        print("✓ PRONTO format validation passed")
        return pronto_code
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None

def test_round_trip():
    """Test round-trip conversion: custom -> PRONTO -> Broadlink."""
    print("\nTesting round-trip conversion...")
    
    custom_code = "3;0x1FE50AF;32;0"
    
    try:
        # Convert to PRONTO
        pronto_code = custom_to_pronto(custom_code)
        
        # Convert PRONTO to Broadlink
        broadlink_data = pronto_to_broadlink(pronto_code)
        b64_code = base64.b64encode(broadlink_data).decode()
        
        print(f"✓ Round-trip conversion successful")
        print(f"  Custom: {custom_code}")
        print(f"  PRONTO: {len(pronto_code.split())} values")
        print(f"  Broadlink: {len(broadlink_data)} bytes -> {len(b64_code)} base64 chars")
        
        return True
        
    except Exception as e:
        print(f"✗ Round-trip failed: {e}")
        return False

def test_nec_direct_conversion():
    """Test direct NEC format conversion."""
    print("\nTesting direct NEC format conversion...")
    
    test_cases = [
        ("0x1FE50AF", "Raw hex with 0x prefix"),
        ("1FE50AF", "Raw hex without prefix"),
        ("FE AF", "Address/Command pair"),
        ("0xFE 0xAF", "Address/Command pair with 0x"),
    ]
    
    passed = 0
    for nec_code, description in test_cases:
        try:
            broadlink_data = nec_to_broadlink(nec_code)
            b64_code = base64.b64encode(broadlink_data).decode()
            
            print(f"✓ {description}: {nec_code} -> {len(broadlink_data)} bytes")
            passed += 1
            
        except Exception as e:
            print(f"✗ {description}: Failed - {e}")
    
    print(f"NEC conversion: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)


def test_nec_validation():
    """Test NEC protocol validation."""
    print("\nTesting NEC protocol validation...")
    
    # Valid NEC code
    valid_nec = "3;0x1FE50AF;32;0"
    
    # Extract NEC components
    hex_val = 0x1FE50AF
    command = (hex_val & 0xFF)
    command_inv = ((hex_val >> 8) & 0xFF)
    address = ((hex_val >> 16) & 0xFF)
    address_inv = ((hex_val >> 24) & 0xFF)
    
    addr_valid = (address + address_inv) == 255
    cmd_valid = (command + command_inv) == 255
    
    print(f"  Address: 0x{address:02X} + 0x{address_inv:02X} = {address + address_inv} {'✓' if addr_valid else '✗'}")
    print(f"  Command: 0x{command:02X} + 0x{command_inv:02X} = {command + command_inv} {'✓' if cmd_valid else '✗'}")
    
    if addr_valid and cmd_valid:
        print("✓ NEC validation passed")
        return True
    else:
        print("✗ NEC validation failed")
        return False

def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\nTesting error handling...")
    
    test_cases = [
        ("", "Empty string"),
        ("invalid", "Invalid format"),
        ("1;2;3", "Too few parts"),
        ("1;2;3;4;5", "Too many parts"),
        ("invalid;0x1234;32;0", "Invalid protocol"),
        ("3;invalid;32;0", "Invalid hex value"),
        ("3;0x1234;invalid;0", "Invalid bits"),
        ("3;0x1234;32;invalid", "Invalid repeat"),
        ("99;0x1234;32;0", "Unsupported protocol"),
    ]
    
    passed = 0
    for test_input, description in test_cases:
        try:
            custom_to_pronto(test_input)
            print(f"✗ {description}: Should have raised an error")
        except ValueError:
            print(f"✓ {description}: Correctly raised ValueError")
            passed += 1
        except Exception as e:
            print(f"? {description}: Unexpected error type: {e}")
    
    print(f"Error handling: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)

def main():
    """Run all tests."""
    print("IR Code Converter Test Suite")
    print("=" * 40)
    
    tests = [
        test_custom_to_pronto,
        test_round_trip,
        test_nec_direct_conversion,
        test_nec_validation,
        test_error_handling,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())