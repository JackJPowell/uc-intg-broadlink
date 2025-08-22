/**
 * Simple test suite for the JavaScript IR converter
 * 
 * This is a basic test suite to validate the JavaScript implementation
 * matches the behavior of the Python version.
 */

const BroadlinkIRConverter = require('./ir_converter.js');

class SimpleTest {
    constructor() {
        this.tests = [];
        this.passed = 0;
        this.failed = 0;
    }

    test(description, testFn) {
        this.tests.push({ description, testFn });
    }

    assertEqual(actual, expected, message = "") {
        if (actual !== expected) {
            throw new Error(`Expected ${expected}, got ${actual}. ${message}`);
        }
    }

    assertTrue(value, message = "") {
        if (!value) {
            throw new Error(`Expected true, got ${value}. ${message}`);
        }
    }

    assertArrayEqual(actual, expected, message = "") {
        if (actual.length !== expected.length) {
            throw new Error(`Array lengths differ: ${actual.length} vs ${expected.length}. ${message}`);
        }
        for (let i = 0; i < actual.length; i++) {
            if (actual[i] !== expected[i]) {
                throw new Error(`Arrays differ at index ${i}: ${actual[i]} vs ${expected[i]}. ${message}`);
            }
        }
    }

    expectError(testFn, expectedErrorMessage = null) {
        try {
            testFn();
            throw new Error("Expected an error but none was thrown");
        } catch (error) {
            if (expectedErrorMessage && !error.message.includes(expectedErrorMessage)) {
                throw new Error(`Expected error containing "${expectedErrorMessage}", got "${error.message}"`);
            }
        }
    }

    run() {
        console.log("Running JavaScript IR Converter Tests");
        console.log("====================================");

        for (const { description, testFn } of this.tests) {
            try {
                testFn();
                console.log(`✅ ${description}`);
                this.passed++;
            } catch (error) {
                console.log(`❌ ${description}: ${error.message}`);
                this.failed++;
            }
        }

        console.log(`\nResults: ${this.passed} passed, ${this.failed} failed`);
        return this.failed === 0;
    }
}

// Test suite
const test = new SimpleTest();
const converter = new BroadlinkIRConverter();

test.test("should convert valid HEX code", () => {
    const hexCode = "26001A00";
    const result = converter.hexToBroadlink(hexCode);
    
    test.assertTrue(result instanceof Uint8Array);
    test.assertTrue(converter.validateBroadlinkPacket(result));
    test.assertEqual(result[0], 0x26); // Command type
    test.assertEqual(result[1], 0x00); // Command repeat
    test.assertEqual(result.length % 16, 0); // Multiple of 16
});

test.test("should handle whitespace in HEX code", () => {
    const hexCode = "26 00 1A 00";
    const result = converter.hexToBroadlink(hexCode);
    test.assertTrue(converter.validateBroadlinkPacket(result));
});

test.test("should throw error for empty HEX code", () => {
    test.expectError(() => converter.hexToBroadlink(""), "cannot be empty");
});

test.test("should throw error for odd length HEX code", () => {
    test.expectError(() => converter.hexToBroadlink("ABC"), "even number of characters");
});

test.test("should throw error for invalid HEX characters", () => {
    test.expectError(() => converter.hexToBroadlink("XYZW"), "Invalid HEX code format");
});

test.test("should produce same output as Python version", () => {
    const hexCode = "26001A00AC005D005D00180018005D005D005D0018001800180018005D001800000D05";
    const result = converter.hexToBroadlink(hexCode);
    const b64Code = converter.bytesToBase64(result);
    
    // This should match the Python version output
    const expectedB64 = "JgAjACYAGgCsAF0AXQAYABgAXQBdAF0AGAAYABgAGABdABgAAA0FAAAAAAAAAAAA";
    test.assertEqual(b64Code, expectedB64);
});

test.test("should validate packets correctly", () => {
    const validPacket = converter.hexToBroadlink("26001A00");
    test.assertTrue(converter.validateBroadlinkPacket(validPacket));
    
    // Test invalid packets
    const shortPacket = new Uint8Array([0x26, 0x00]); // Too short
    test.assertEqual(converter.validateBroadlinkPacket(shortPacket), false);
    
    const wrongType = new Uint8Array(16);
    wrongType[0] = 0x25; // Wrong command type
    test.assertEqual(converter.validateBroadlinkPacket(wrongType), false);
    
    const wrongLength = new Uint8Array(8); // Not multiple of 16
    wrongLength[0] = 0x26;
    test.assertEqual(converter.validateBroadlinkPacket(wrongLength), false);
});

test.test("should handle base64 conversion correctly", () => {
    const hexCode = "26001A00";
    const result = converter.hexToBroadlink(hexCode);
    const b64Code = converter.bytesToBase64(result);
    const decoded = converter.base64ToBytes(b64Code);
    
    test.assertArrayEqual(result, decoded);
});

test.test("should handle hex to bytes conversion", () => {
    const hex = "26001A00";
    const bytes = converter.hexToBytes(hex);
    const expected = new Uint8Array([0x26, 0x00, 0x1A, 0x00]);
    
    test.assertArrayEqual(bytes, expected);
});

test.test("should create proper packet structure", () => {
    const pulseData = new Uint8Array([0xAC, 0x00, 0x5D, 0x00]);
    const packet = converter.createBroadlinkPacket(pulseData);
    
    test.assertEqual(packet[0], 0x26); // Command type
    test.assertEqual(packet[1], 0x00); // Command repeat
    test.assertEqual(packet[2], 0x04); // Payload length (little-endian low byte)
    test.assertEqual(packet[3], 0x00); // Payload length (little-endian high byte)
    
    // Check pulse data is copied correctly
    for (let i = 0; i < pulseData.length; i++) {
        test.assertEqual(packet[4 + i], pulseData[i]);
    }
    
    // Check padding
    test.assertEqual(packet.length % 16, 0);
});

// Run the tests
const success = test.run();
process.exit(success ? 0 : 1);