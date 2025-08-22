# IR Code Converter

This module provides functions to convert HEX, PRONTO, NEC, and custom IR codes into the Broadlink IR raw format, with support for converting between different IR formats.

## Overview

The IR converter allows you to convert infrared remote control codes from common formats (HEX, PRONTO, NEC, and custom semicolon-separated format) into the Broadlink device format. This is useful when you have IR codes from other sources and want to use them with Broadlink devices.

## Supported Formats

### HEX Format
Raw hexadecimal IR pulse data. Example:
```
26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05
```

### PRONTO Format
Philips Pronto remote control format. Example:
```
0000 006C 0022 0002 015B 00AD 0016 0041 0016 0041 0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 0016 0041 0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 0016 0016 0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 0016 0016 0016 0041 0016 0041 0016 0041 0016 0041 0016 0041 0016 0041 0016 06A4 015B 0057 0016 0E6C
```

### NEC Format
NEC protocol IR codes in various representations:

#### Raw Hex Format
32-bit hex values representing NEC protocol. Examples:
```
0x1FE50AF    # With 0x prefix
1FE50AF      # Without prefix
```

#### Address/Command Pair Format
Separate address and command values. Examples:
```
FE AF        # Without 0x prefix
0xFE 0xAF    # With 0x prefix
```

### Custom Format
Semicolon-separated format for IR learning devices. Format: `protocol;hex_value;bits;repeat`

Example:
```
3;0x1FE50AF;32;0
```

Where:
- `protocol`: Protocol type (3 = NEC protocol)
- `hex_value`: IR code value in hexadecimal (with or without 0x prefix)
- `bits`: Number of bits (32 for standard NEC)
- `repeat`: Repeat count (usually 0)

## Usage

### Command Line Tool

A convenient CLI tool is provided for converting between IR formats:

```bash
# Convert NEC hex to Broadlink format (auto-detect)
python tools/ir_code_converter.py "0x1FE50AF"

# Convert NEC address/command pair to Broadlink format
python tools/ir_code_converter.py "FE AF"

# Convert custom format to Broadlink format
python tools/ir_code_converter.py "3;0x1FE50AF;32;0"

# Convert PRONTO to Broadlink format
python tools/ir_code_converter.py "0000 006C 0043 0000 ..."

# Show detailed analysis
python tools/ir_code_converter.py "0x1FE50AF" --analyze

# Specify input format explicitly
python tools/ir_code_converter.py "1FE50AF" --input-format nec
```

### Direct Conversion

```python
from intg_broadlink.ir_converter import (
    hex_to_broadlink, 
    pronto_to_broadlink, 
    nec_to_broadlink, 
    custom_to_pronto
)
import base64

# Convert HEX code
hex_code = "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05"
broadlink_data = hex_to_broadlink(hex_code)
b64_code = base64.b64encode(broadlink_data).decode()

# Convert PRONTO code
pronto_code = "0000 006C 0022 0002 015B 00AD ..."
broadlink_data = pronto_to_broadlink(pronto_code)
b64_code = base64.b64encode(broadlink_data).decode()

# Convert NEC hex format
nec_code = "0x1FE50AF"
broadlink_data = nec_to_broadlink(nec_code)
b64_code = base64.b64encode(broadlink_data).decode()

# Convert NEC address/command pair
nec_code = "FE AF"
broadlink_data = nec_to_broadlink(nec_code)
b64_code = base64.b64encode(broadlink_data).decode()

# Convert custom format to PRONTO
custom_code = "3;0x1FE50AF;32;0"
pronto_code = custom_to_pronto(custom_code)

# Convert custom format to Broadlink (via PRONTO)
pronto_code = custom_to_pronto(custom_code)
broadlink_data = pronto_to_broadlink(pronto_code)
b64_code = base64.b64encode(broadlink_data).decode()
```

### Using Broadlink Class Integration

```python
from intg_broadlink.rm import Broadlink

# Assuming you have a Broadlink instance
broadlink = Broadlink(device, config)

# Convert with auto-detection
b64_code = broadlink.convert_ir_code(your_ir_code)

# Convert specific formats
b64_code = broadlink.convert_ir_code(hex_code, "hex")
b64_code = broadlink.convert_ir_code(pronto_code, "pronto")
b64_code = broadlink.convert_ir_code(nec_code, "nec")
b64_code = broadlink.convert_ir_code(custom_code, "custom")

# Examples with different NEC formats
b64_code = broadlink.convert_ir_code("0x1FE50AF", "nec")      # Raw hex
b64_code = broadlink.convert_ir_code("FE AF", "nec")          # Address/Command
b64_code = broadlink.convert_ir_code("3;0x1FE50AF;32;0", "custom")  # Custom format

# Convert custom format to PRONTO (backward compatibility)
pronto_code = broadlink.convert_to_pronto(custom_code, "custom")
```

## Broadlink IR Format

The converter outputs data in the Broadlink IR raw format, which consists of:

1. **Header**: 
   - Command Type (0x26 for IR)
   - Command Repeat (0x00 for no repeat)  
   - Command Length (little-endian 16-bit)

2. **Pulse Data**:
   - Alternating ON and OFF durations
   - Timing in 32.84μs units
   - Long durations (>255) use 3-byte encoding: 0x00 + 16-bit big-endian value

3. **Padding**: 
   - Zero-padded to multiple of 16 bytes for AES encryption

## Functions

### `hex_to_broadlink(hex_code: str) -> bytes`
Converts a HEX IR code string to Broadlink format.

**Parameters:**
- `hex_code`: Hexadecimal string (even length, no spaces)

**Returns:** Raw Broadlink IR data as bytes

**Raises:** `ValueError` for invalid input

### `pronto_to_broadlink(pronto_code: str) -> bytes`
Converts a PRONTO IR code string to Broadlink format.

**Parameters:**
- `pronto_code`: PRONTO format string (space-separated hex values)

**Returns:** Raw Broadlink IR data as bytes

**Raises:** `ValueError` for invalid input

### `custom_to_pronto(custom_code: str) -> str`
Converts a custom semicolon-separated IR code to PRONTO format.

**Parameters:**
- `custom_code`: Custom format string (protocol;hex_value;bits;repeat)

**Returns:** PRONTO format IR code string

**Raises:** `ValueError` for invalid input or unsupported protocol

**Supported Protocols:**
- Protocol 3: NEC IR protocol

### `validate_broadlink_packet(packet: bytes) -> bool`
Validates if a packet follows the Broadlink IR format.

**Parameters:**
- `packet`: Broadlink IR packet bytes

**Returns:** `True` if format is valid

## Error Handling

The converter functions include comprehensive error handling:
- Empty or invalid input validation
- Format-specific validation (hex format, PRONTO structure)
- Overflow protection for timing values
- Proper exception messages

## Examples

### Converting Custom Format to PRONTO

```python
from intg_broadlink.ir_converter import custom_to_pronto

# Convert the example from the problem statement
custom_code = "3;0x1FE50AF;32;0"
pronto_code = custom_to_pronto(custom_code)
print(pronto_code)
# Output: 0000 006C 0043 0000 0156 00AB 0015 0040 0015 0040 ...
```

### Using the CLI Tool

```bash
# Convert to PRONTO format with analysis
python tools/ir_code_converter.py "3;0x1FE50AF;32;0" --analyze

# Convert to Broadlink format
python tools/ir_code_converter.py "3;0x1FE50AF;32;0" --output-format broadlink
```

### NEC Protocol Analysis

The custom format `3;0x1FE50AF;32;0` represents:
- Protocol 3 (NEC)
- Address: 0xFE, Inverted Address: 0x01
- Command: 0xAF, Inverted Command: 0x50
- Valid NEC format (address + ~address = 255, command + ~command = 255)

See `tools/ir_code_converter.py` for complete usage examples.

## Testing

Run the test suite:
```bash
python test_ir_converter.py
python test_integration.py
```

Test the CLI tool:
```bash
python tools/ir_code_converter.py "3;0x1FE50AF;32;0" --analyze
```

## Integration Notes

- The IR converter is designed to integrate seamlessly with existing Broadlink functionality
- Converted codes can be used directly with `device.send_data()`
- Base64 encoding is handled automatically when using the Broadlink class integration
- Auto-detection between HEX and PRONTO formats is supported