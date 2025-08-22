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

from ir_converter import custom_to_pronto, pronto_to_broadlink, nec_to_broadlink
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

def convert_to_broadlink(input_code: str, input_format: str = "auto") -> str:
    """Convert input code to Broadlink format (base64)."""
    try:
        if input_format == "auto":
            input_format = detect_format(input_code)
        
        if input_format == "custom":
            # First convert to PRONTO
            pronto_code = custom_to_pronto(input_code)
            # Then convert PRONTO to Broadlink
            broadlink_data = pronto_to_broadlink(pronto_code)
        elif input_format == "nec":
            # Direct NEC to Broadlink conversion
            broadlink_data = nec_to_broadlink(input_code)
        elif input_format == "pronto":
            # Direct PRONTO to Broadlink conversion
            broadlink_data = pronto_to_broadlink(input_code)
        else:
            raise ValueError(f"Unsupported input format: {input_format}")
            
        # Encode as base64
        return base64.b64encode(broadlink_data).decode()
    except Exception as e:
        raise ValueError(f"Failed to convert to Broadlink: {e}")


def detect_format(code: str) -> str:
    """Detect the format of the input code."""
    code = code.strip()
    
    # Check for custom semicolon-separated format
    if ";" in code and code.count(";") == 3:
        return "custom"
        
    # Check for PRONTO format
    if code.startswith("0000 ") or (" " in code and not is_nec_format(code)):
        return "pronto"
        
    # Check for NEC format
    if is_nec_format(code):
        return "nec"
        
    return "unknown"


def is_nec_format(code: str) -> bool:
    """Check if code is in NEC format."""
    code = code.strip()
    
    # Check for address/command pair format: "FE AF" or "0xFE 0xAF"
    if ' ' in code:
        parts = code.split()
        if len(parts) == 2:
            try:
                # Try to parse both parts as hex
                for part in parts:
                    if part.startswith('0x') or part.startswith('0X'):
                        int(part, 16)
                    else:
                        int(part, 16)
                return True
            except ValueError:
                return False
    
    # Check for raw hex format (typically 6-8 hex chars for NEC)
    if code.startswith('0x') or code.startswith('0X'):
        hex_part = code[2:]
    else:
        hex_part = code
        
    # Check if it's valid hex and reasonable length for NEC (4-8 chars typically)
    if len(hex_part) >= 4 and len(hex_part) <= 8:
        try:
            int(hex_part, 16)
            return True
        except ValueError:
            return False
            
    return False


def convert_to_broadlink_old(custom_code: str) -> str:
    """Convert custom code to Broadlink format (base64) - old version."""
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
        description="Convert IR codes between different formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "3;0x1FE50AF;32;0"                    # Custom format
  %(prog)s "0x1FE50AF"                           # NEC hex format
  %(prog)s "FE AF"                               # NEC address/command
  %(prog)s "0000 006C 0043 0000 ..."            # PRONTO format
  %(prog)s "3;0x1FE50AF;32;0" --output-format broadlink --verbose
  %(prog)s "0x1FE50AF" --analyze

Supported input formats:
  - Custom: protocol;hex_value;bits;repeat (e.g., "3;0x1FE50AF;32;0")
  - NEC hex: 0x1FE50AF or 1FE50AF
  - NEC addr/cmd: "FE AF" or "0xFE 0xAF"
  - PRONTO: "0000 006C 0043 0000 ..."
        """
    )
    
    parser.add_argument(
        "code",
        help="IR code in any supported format"
    )
    
    parser.add_argument(
        "--input-format", "-i",
        choices=["auto", "custom", "nec", "pronto"],
        default="auto",
        help="Input format (default: auto-detect)"
    )
    
    parser.add_argument(
        "--output-format", "-f",
        choices=["pronto", "broadlink"],
        default="broadlink",
        help="Output format (default: broadlink)"
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
    
    try:
        # Detect input format if auto
        input_format = args.input_format
        if input_format == "auto":
            input_format = detect_format(args.code)
            if input_format == "unknown":
                print("Error: Unable to detect input format. Please specify --input-format", file=sys.stderr)
                sys.exit(1)
        
        print(f"Input: {args.code}")
        print(f"Detected format: {input_format.upper()}")
        print(f"Output format: {args.output_format.upper()}")
        print()
        
        # Show analysis if requested
        if args.analyze:
            if input_format == "custom":
                analyze_nec_code(args.code)
            elif input_format == "nec":
                analyze_nec_hex(args.code)
            print()
        
        if args.output_format == "pronto":
            if input_format == "custom":
                result = convert_to_pronto(args.code)
            elif input_format == "nec":
                # Convert NEC to Broadlink first, then extract PRONTO via reverse
                # For now, convert via PRONTO intermediate
                broadlink_data = nec_to_broadlink(args.code)
                # For display, we'll show that we can convert NEC to Broadlink
                print("NEC format detected. Converting to Broadlink format instead.")
                result = base64.b64encode(broadlink_data).decode()
                print("Broadlink Code (Base64):")
                print(result)
                return
            elif input_format == "pronto":
                result = args.code  # Already PRONTO
            else:
                raise ValueError(f"Cannot convert {input_format} to PRONTO")
                
            print("PRONTO Code:")
            print(format_pronto_output(result))
            
        elif args.output_format == "broadlink":
            result = convert_to_broadlink(args.code, input_format)
            print("Broadlink Code (Base64):")
            print(result)
        
        print("\nConversion completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def analyze_nec_hex(nec_code: str):
    """Analyze NEC hex format."""
    nec_code = nec_code.strip()
    
    try:
        if ' ' in nec_code:
            # Address/Command pair format
            parts = nec_code.split()
            addr = int(parts[0], 16) if parts[0].startswith('0x') else int(parts[0], 16)
            cmd = int(parts[1], 16) if parts[1].startswith('0x') else int(parts[1], 16)
            
            print(f"NEC Address/Command Analysis:")
            print(f"  Address: 0x{addr:02X} (binary: {addr:08b})")
            print(f"  Command: 0x{cmd:02X} (binary: {cmd:08b})")
            
        else:
            # Raw hex format
            if nec_code.startswith('0x') or nec_code.startswith('0X'):
                nec_value = int(nec_code, 16)
            else:
                nec_value = int(nec_code, 16)
                
            command = (nec_value & 0xFF)
            command_inv = ((nec_value >> 8) & 0xFF)
            address = ((nec_value >> 16) & 0xFF)
            address_inv = ((nec_value >> 24) & 0xFF)
            
            print(f"NEC Raw Hex Analysis:")
            print(f"  Input: {nec_code} -> 0x{nec_value:08X}")
            print(f"  Address: 0x{address:02X} (binary: {address:08b})")
            print(f"  ~Address: 0x{address_inv:02X} (binary: {address_inv:08b})")
            print(f"  Command: 0x{command:02X} (binary: {command:08b})")
            print(f"  ~Command: 0x{command_inv:02X} (binary: {command_inv:08b})")
            
            addr_valid = (address + address_inv) == 255
            cmd_valid = (command + command_inv) == 255
            print(f"  Address validation: {'✓' if addr_valid else '✗'} ({address} + {address_inv} = {address + address_inv})")
            print(f"  Command validation: {'✓' if cmd_valid else '✗'} ({command} + {command_inv} = {command + command_inv})")
            
    except ValueError as e:
        print(f"Error analyzing NEC code: {e}")

if __name__ == "__main__":
    main()