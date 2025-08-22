#!/usr/bin/env python3
"""
IR Code Converter CLI Tool

A command-line utility to convert IR codes between different formats.
Supports custom semicolon-separated format to PRONTO format conversion.

Usage:
    python ir_code_converter.py "3;0x1FE50AF;32;0"
    python ir_code_converter.py "3;0x1FE50AF;32;0" --output-format pronto
    python ir_code_converter.py "3;0x1FE50AF;32;0" --output-format broadlink
"""

import sys
import argparse
import logging
from pathlib import Path

# Add the intg-broadlink directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "intg-broadlink"))

from ir_converter import custom_to_pronto, pronto_to_broadlink
import base64

def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )

def convert_to_pronto(custom_code: str) -> str:
    """Convert custom code to PRONTO format."""
    try:
        pronto_code = custom_to_pronto(custom_code)
        return pronto_code
    except Exception as e:
        raise ValueError(f"Failed to convert to PRONTO: {e}")

def convert_to_broadlink(custom_code: str) -> str:
    """Convert custom code to Broadlink format (base64)."""
    try:
        # First convert to PRONTO
        pronto_code = custom_to_pronto(custom_code)
        # Then convert PRONTO to Broadlink
        broadlink_data = pronto_to_broadlink(pronto_code)
        # Encode as base64
        return base64.b64encode(broadlink_data).decode()
    except Exception as e:
        raise ValueError(f"Failed to convert to Broadlink: {e}")

def validate_custom_format(code: str) -> bool:
    """Validate that the code is in the expected custom format."""
    parts = code.split(';')
    if len(parts) != 4:
        return False
    
    try:
        protocol = int(parts[0])
        hex_value = int(parts[1], 16) if parts[1].startswith('0x') else int(parts[1], 16)
        bits = int(parts[2])
        repeat = int(parts[3])
        return True
    except ValueError:
        return False

def analyze_nec_code(custom_code: str):
    """Analyze and display NEC code components."""
    parts = custom_code.split(';')
    if len(parts) != 4:
        return
    
    try:
        protocol = int(parts[0])
        hex_value = int(parts[1], 16) if parts[1].startswith('0x') else int(parts[1], 16)
        bits = int(parts[2])
        repeat = int(parts[3])
        
        print(f"Input Analysis:")
        print(f"  Protocol: {protocol} {'(NEC)' if protocol == 3 else '(Unknown)'}")
        print(f"  Hex Value: 0x{hex_value:08X}")
        print(f"  Bits: {bits}")
        print(f"  Repeat: {repeat}")
        
        if protocol == 3 and bits == 32:  # NEC protocol
            command = (hex_value & 0xFF)
            command_inv = ((hex_value >> 8) & 0xFF)
            address = ((hex_value >> 16) & 0xFF)
            address_inv = ((hex_value >> 24) & 0xFF)
            
            print(f"\nNEC Protocol Breakdown:")
            print(f"  Address: 0x{address:02X} (binary: {address:08b})")
            print(f"  ~Address: 0x{address_inv:02X} (binary: {address_inv:08b})")
            print(f"  Command: 0x{command:02X} (binary: {command:08b})")
            print(f"  ~Command: 0x{command_inv:02X} (binary: {command_inv:08b})")
            
            addr_valid = (address + address_inv) == 255
            cmd_valid = (command + command_inv) == 255
            print(f"  Address validation: {'✓' if addr_valid else '✗'} ({address} + {address_inv} = {address + address_inv})")
            print(f"  Command validation: {'✓' if cmd_valid else '✗'} ({command} + {command_inv} = {command + command_inv})")
            
    except ValueError as e:
        print(f"Error analyzing code: {e}")

def format_pronto_output(pronto_code: str) -> str:
    """Format PRONTO code for better readability."""
    parts = pronto_code.split()
    lines = []
    
    # First line: header
    lines.append(" ".join(parts[:4]))
    
    # Remaining lines: 8 values per line
    remaining = parts[4:]
    for i in range(0, len(remaining), 8):
        lines.append(" ".join(remaining[i:i+8]))
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Convert IR codes from custom format to PRONTO or Broadlink format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "3;0x1FE50AF;32;0"
  %(prog)s "3;0x1FE50AF;32;0" --output-format pronto
  %(prog)s "3;0x1FE50AF;32;0" --output-format broadlink --verbose
  %(prog)s "3;0x1FE50AF;32;0" --analyze

Input format: protocol;hex_value;bits;repeat
  - protocol: 3 for NEC protocol
  - hex_value: IR code in hexadecimal (with or without 0x prefix)
  - bits: Number of bits (32 for standard NEC)
  - repeat: Repeat count (usually 0)
        """
    )
    
    parser.add_argument(
        "code",
        help="IR code in custom format (e.g., '3;0x1FE50AF;32;0')"
    )
    
    parser.add_argument(
        "--output-format", "-f",
        choices=["pronto", "broadlink"],
        default="pronto",
        help="Output format (default: pronto)"
    )
    
    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Show detailed analysis of the input code"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Validate input format
    if not validate_custom_format(args.code):
        print("Error: Invalid input format. Expected: protocol;hex_value;bits;repeat", file=sys.stderr)
        print("Example: 3;0x1FE50AF;32;0", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Show analysis if requested
        if args.analyze:
            analyze_nec_code(args.code)
            print()
        
        print(f"Converting: {args.code}")
        print(f"Output format: {args.output_format.upper()}")
        print()
        
        if args.output_format == "pronto":
            result = convert_to_pronto(args.code)
            print("PRONTO Code:")
            print(format_pronto_output(result))
        elif args.output_format == "broadlink":
            result = convert_to_broadlink(args.code)
            print("Broadlink Code (Base64):")
            print(result)
        
        print("\nConversion completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()