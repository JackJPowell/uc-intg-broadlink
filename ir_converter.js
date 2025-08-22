/**
 * JavaScript IR Code Converter for Broadlink devices
 * 
 * This is a JavaScript port of the Python IR converter functionality.
 * It provides functions to convert HEX IR codes to Broadlink format.
 * 
 * Note: This is a simplified version focusing on HEX conversion.
 * For full functionality including PRONTO and NEC support, use the Python version.
 */

class BroadlinkIRConverter {
    constructor() {
        this.BROADLINK_TICK = 32.84; // microseconds per tick
        this.IR_COMMAND_TYPE = 0x26; // Command type for IR
    }

    /**
     * Convert HEX IR code to Broadlink IR raw format.
     * @param {string} hexCode - Hexadecimal string representing IR pulse data
     * @returns {Uint8Array} Broadlink IR raw format data
     * @throws {Error} If hexCode is invalid or empty
     */
    hexToBroadlink(hexCode) {
        if (!hexCode) {
            throw new Error("HEX code cannot be empty");
        }

        // Remove any whitespace and ensure even length
        hexCode = hexCode.replace(/\s/g, "");
        if (hexCode.length % 2 !== 0) {
            throw new Error("HEX code must have even number of characters");
        }

        try {
            // Convert hex string to bytes
            const rawData = this.hexToBytes(hexCode);
            // Create Broadlink packet
            return this.createBroadlinkPacket(rawData);
        } catch (e) {
            throw new Error(`Invalid HEX code format: ${e.message}`);
        }
    }

    /**
     * Convert hex string to byte array
     * @param {string} hex - Hex string
     * @returns {Uint8Array} Byte array
     */
    hexToBytes(hex) {
        const bytes = new Uint8Array(hex.length / 2);
        for (let i = 0; i < hex.length; i += 2) {
            const byte = parseInt(hex.substr(i, 2), 16);
            if (isNaN(byte)) {
                throw new Error(`Invalid hex character at position ${i}`);
            }
            bytes[i / 2] = byte;
        }
        return bytes;
    }

    /**
     * Create a complete Broadlink IR packet with headers.
     * @param {Uint8Array} pulseData - Raw pulse timing data
     * @returns {Uint8Array} Complete Broadlink IR packet
     */
    createBroadlinkPacket(pulseData) {
        // Create packet header
        const header = new Uint8Array(4);
        header[0] = this.IR_COMMAND_TYPE; // Command type (0x26 for IR)
        header[1] = 0x00; // Command repeat (0x00 for no repeat)

        // Add payload length (little-endian 16-bit)
        const payloadLength = pulseData.length;
        header[2] = payloadLength & 0xFF;
        header[3] = (payloadLength >> 8) & 0xFF;

        // Combine header and pulse data
        const packet = new Uint8Array(header.length + pulseData.length);
        packet.set(header, 0);
        packet.set(pulseData, header.length);

        // Pad to multiple of 16 bytes for AES encryption
        const paddingNeeded = (16 - (packet.length % 16)) % 16;
        if (paddingNeeded > 0) {
            const paddedPacket = new Uint8Array(packet.length + paddingNeeded);
            paddedPacket.set(packet, 0);
            // Remaining bytes are already 0 in new Uint8Array
            return paddedPacket;
        }

        return packet;
    }

    /**
     * Validate a Broadlink IR packet format.
     * @param {Uint8Array} packet - Broadlink IR packet to validate
     * @returns {boolean} True if packet format is valid
     */
    validateBroadlinkPacket(packet) {
        if (packet.length < 4) {
            return false;
        }

        // Check command type
        if (packet[0] !== this.IR_COMMAND_TYPE) {
            return false;
        }

        // Check packet length is multiple of 16
        if (packet.length % 16 !== 0) {
            return false;
        }

        // Extract and verify payload length
        const payloadLength = packet[2] | (packet[3] << 8);
        let expectedTotalLength = 4 + payloadLength;

        // Account for padding
        if (expectedTotalLength % 16 !== 0) {
            expectedTotalLength += 16 - (expectedTotalLength % 16);
        }

        return packet.length === expectedTotalLength;
    }

    /**
     * Convert Uint8Array to base64 string
     * @param {Uint8Array} bytes - Byte array
     * @returns {string} Base64 encoded string
     */
    bytesToBase64(bytes) {
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    /**
     * Convert base64 string to Uint8Array
     * @param {string} base64 - Base64 encoded string
     * @returns {Uint8Array} Byte array
     */
    base64ToBytes(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes;
    }
}

// Example usage
function exampleUsage() {
    const converter = new BroadlinkIRConverter();
    
    console.log("JavaScript IR Code Converter Example");
    console.log("====================================");
    
    try {
        // Convert HEX code
        const hexCode = "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05";
        console.log(`\nHEX Code: ${hexCode}`);
        
        const broadlinkData = converter.hexToBroadlink(hexCode);
        const b64Code = converter.bytesToBase64(broadlinkData);
        
        console.log(`Broadlink (Base64): ${b64Code}`);
        console.log(`Packet valid: ${converter.validateBroadlinkPacket(broadlinkData)}`);
        console.log(`Packet length: ${broadlinkData.length} bytes`);
        
        // Test round-trip conversion
        const decoded = converter.base64ToBytes(b64Code);
        const isIdentical = broadlinkData.every((val, i) => val === decoded[i]);
        console.log(`Round-trip conversion successful: ${isIdentical}`);
        
    } catch (error) {
        console.error(`Error: ${error.message}`);
    }
    
    // Test error handling
    console.log("\nError handling examples:");
    
    try {
        converter.hexToBroadlink("");
    } catch (error) {
        console.log(`Empty HEX error: ${error.message}`);
    }
    
    try {
        converter.hexToBroadlink("ABC");
    } catch (error) {
        console.log(`Odd length HEX error: ${error.message}`);
    }
    
    try {
        converter.hexToBroadlink("XYZW");
    } catch (error) {
        console.log(`Invalid HEX characters error: ${error.message}`);
    }
}

// Export for Node.js or browser usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BroadlinkIRConverter;
} else if (typeof window !== 'undefined') {
    window.BroadlinkIRConverter = BroadlinkIRConverter;
}

// Run example if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
    exampleUsage();
}