# IR Code Converter

This module provides functions to convert HEX and PRONTO IR codes into the Broadlink IR raw format.

## Overview

The IR converter allows you to convert infrared remote control codes from common formats (HEX and PRONTO) into the Broadlink device format. This is useful when you have IR codes from other sources and want to use them with Broadlink devices.

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

## Usage

### Direct Conversion

```python
from intg_broadlink.ir_converter import hex_to_broadlink, pronto_to_broadlink
import base64

# Convert HEX code
hex_code = "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05"
broadlink_data = hex_to_broadlink(hex_code)
b64_code = base64.b64encode(broadlink_data).decode()

# Convert PRONTO code
pronto_code = "0000 006C 0022 0002 015B 00AD ..."
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

# Convert specific format
b64_code = broadlink.convert_ir_code(hex_code, "hex")
b64_code = broadlink.convert_ir_code(pronto_code, "pronto")
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

See `example_ir_converter.py` for complete usage examples.

## Testing

Run the test suite:
```bash
python test_ir_converter.py
python test_integration.py
```

## Integration Notes

- The IR converter is designed to integrate seamlessly with existing Broadlink functionality
- Converted codes can be used directly with `device.send_data()`
- Base64 encoding is handled automatically when using the Broadlink class integration
- Auto-detection between HEX and PRONTO formats is supported