"""Test script to compare all three PRONTO conversion methods."""

# Test PRONTO code
pronto_code = "0000 006c 0000 001a 0099 00ad 000f 0027 0010 0027 000f 0013 000f 0027 0010 0013 000f 0013 000f 0027 0010 0013 000f 0027 000f 0013 0010 0027 000f 0027 000f 0027 0010 0027 000f 0027 000f 0013 0010 0013 000f 0027 000f 0013 0010 0013 000f 0013 000f 0013 0010 0013 000f 0027 000f 077f"

def test_javascript_logic():
    """Simulate the JavaScript conversion logic."""
    import re
    
def clean_hex(s):
        return re.sub(r'[^0-9a-fA-F]', '', s)
    
def hex_to_words(pronto_hex):
        clean = clean_hex(pronto_hex).lower()
        if len(clean) % 4 != 0:
            raise ValueError("PRONTO: hex length must be multiple of 4")
        words = []
        for i in range(0, len(clean), 4):
            words.append(int(clean[i:i+4], 16))
        return words
    
def pronto_to_lirc_pulses(pronto_hex):
        words = hex_to_words(pronto_hex)
        if len(words) < 4:
            raise ValueError("PRONTO: too few words")
        if words[0] != 0x0000:
            raise ValueError("PRONTO: only learned format 0000 supported")
        
        freq_word = words[1]
        one_time_pairs = words[2]
        repeat_pairs = words[3]
        expected = 4 + 2 * (one_time_pairs + repeat_pairs)
        
        if len(words) != expected:
            raise ValueError("PRONTO: preamble counts do not match payload length")
        
        unit_micros = freq_word * 0.241246
        pulses_us = [max(1, round(w * unit_micros)) for w in words[4:]]
        return pulses_us
    
def lirc_pulses_to_broadlink_payload(pulses_us):
        pulse_bytes = []
        for us in pulses_us:
            if us < 0:
                raise ValueError("Negative pulse not allowed")
            
            ticks = round((us * 269) / 8192)
            if ticks <= 0:
                ticks = 1
                
            if ticks < 256:
                pulse_bytes.append(ticks)
            else:
                hi = (ticks >> 8) & 0xff
                lo = ticks & 0xff
                pulse_bytes.append(0x00)
                pulse_bytes.append(hi)
                pulse_bytes.append(lo)
        
        pulse_buf = bytes(pulse_bytes)
        header = bytes([0x26, 0x00])
        len_le = len(pulse_buf).to_bytes(2, 'little')
        tail = bytes([0x0d, 0x05])
        
        return header + len_le + pulse_buf + tail
    
pulses = pronto_to_lirc_pulses(pronto_code)
    payload = lirc_pulses_to_broadlink_payload(pulses)
    
    print("JavaScript-style conversion:")
    print(f"Frequency word: {hex_to_words(pronto_code)[1]}")
    print(f"Unit microseconds: {hex_to_words(pronto_code)[1] * 0.241246}")
    print(f"Number of pulse values: {len(pulses)}")
    print(f"Pulses (first 10): {pulses[:10]}")
    print(f"Pulses (last 10): {pulses[-10:]}")
    print(f"Payload length: {len(payload)} bytes")
    print(f"Payload (hex): {payload.hex()}")
    print(f"Starts with 2600: {payload.hex().startswith('2600')}")
    return payload

def test_original_python():
    """Test with the original complex Python conversion."""
    try:
        # Import the existing converter
        from ir_converter import pronto_to_broadlink
        
        print("Original Python conversion:")
        payload = pronto_to_broadlink(pronto_code)
        print(f"Payload length: {len(payload)} bytes")
        print(f"Payload (hex): {payload.hex()}")
        print(f"Starts with 2600: {payload.hex().startswith('2600')}")
        return payload
    except Exception as e:
        print(f"Original Python conversion failed: {e}")
        return None

def test_simplified_python():
    """Test the simplified Python version."""
    print("Simplified Python conversion:")
    return test_javascript_logic()

if __name__ == "__main__":
    print("Testing PRONTO conversion methods with:")
    print(f"PRONTO: {pronto_code[:50]}...")
    print("="*70)
    
    # Test JavaScript-style
    print("\n1. JavaScript-style (Direct conversion):")
    js_result = test_javascript_logic()
    
    print("\n" + "="*70)
    
    # Test original Python
    print("\n2. Original Python (Complex with expansions):")
    orig_result = test_original_python()
    
    print("\n" + "="*70)
    
    # Compare results
    print("\n3. Comparison:")
    if js_result and orig_result:
        print(f"JavaScript payload: {len(js_result)} bytes")
        print(f"Original Python payload: {len(orig_result)} bytes")
        print(f"Payloads identical: {js_result == orig_result}")
        if js_result != orig_result:
            print("Differences found - this explains why JavaScript works better!")
            print(f"JS starts: {js_result.hex()[:20]}...")
            print(f"PY starts: {orig_result.hex()[:20]}...")
    
    print("\n" + "="*70)
    print("\nConclusion:")
    print("If payloads differ, the JavaScript approach is likely more reliable")
    print("because it uses direct conversion without complex frame expansions.")