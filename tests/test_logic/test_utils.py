"""
Test suite for data_formats.utils module.

Tests UTF-8 encoding/decoding utilities and byte sequence handling.
"""
from py_fade.data_formats.utils import missing_bytes_utf_8, try_decode_utf_8, is_equal_utf_8


def test_missing_bytes_utf_8_complete_ascii():
    """
    Test missing_bytes_utf_8 with complete ASCII bytes.

    Flow:
    1. Pass complete ASCII byte sequence
    2. Verify no missing bytes (returns 0)

    Edge cases tested:
    - Simple ASCII characters don't need completion
    """
    assert missing_bytes_utf_8(b"hello") == 0


def test_missing_bytes_utf_8_complete_multibyte():
    """
    Test missing_bytes_utf_8 with complete multibyte UTF-8 sequence.

    Flow:
    1. Pass complete UTF-8 multibyte character
    2. Verify no missing bytes (returns 0)

    Edge cases tested:
    - Complete 2-byte UTF-8 character (é)
    - Complete 3-byte UTF-8 character (€)
    """
    assert missing_bytes_utf_8("é".encode("utf-8")) == 0  # 2-byte character
    assert missing_bytes_utf_8("€".encode("utf-8")) == 0  # 3-byte character


def test_missing_bytes_utf_8_incomplete_sequence():
    """
    Test missing_bytes_utf_8 with incomplete multibyte sequence.

    Flow:
    1. Create strings with truncated UTF-8 multibyte sequences
    2. Verify correct number of missing bytes is returned

    Edge cases tested:
    - Incomplete 2-byte sequence at end (missing 1 byte)
    - Incomplete 3-byte sequence at end (missing 1-2 bytes)
    """
    # 2-byte character truncated - need prefix data for detection
    assert missing_bytes_utf_8(b"hello\xc3") == 1  # Incomplete 2-byte char

    # 3-byte character truncated
    assert missing_bytes_utf_8(b"hello\xe2") == 2  # Only 1 of 3 bytes
    assert missing_bytes_utf_8(b"hello\xe2\x82") == 1  # 2 of 3 bytes


def test_try_decode_utf_8_valid():
    """
    Test try_decode_utf_8 with valid UTF-8 bytes.

    Flow:
    1. Pass valid UTF-8 byte sequences
    2. Verify successful decoding to strings

    Edge cases tested:
    - ASCII characters
    - Multibyte UTF-8 characters
    - Mixed ASCII and multibyte
    """
    assert try_decode_utf_8(b"hello") == "hello"
    assert try_decode_utf_8("café".encode("utf-8")) == "café"
    assert try_decode_utf_8("Hello 世界".encode("utf-8")) == "Hello 世界"


def test_try_decode_utf_8_invalid():
    """
    Test try_decode_utf_8 with invalid UTF-8 bytes.

    Flow:
    1. Pass invalid UTF-8 byte sequences
    2. Verify function returns None

    Edge cases tested:
    - Truncated multibyte sequence
    - Invalid byte patterns
    """
    # Truncated UTF-8 sequence
    assert try_decode_utf_8(b"\xc3") is None

    # Invalid UTF-8 byte
    assert try_decode_utf_8(b"\xff\xfe") is None


def test_is_equal_utf_8_matching():
    """
    Test is_equal_utf_8 with matching bytes and strings.

    Flow:
    1. Compare UTF-8 bytes with equivalent string
    2. Verify equality check returns True

    Edge cases tested:
    - ASCII strings
    - Multibyte UTF-8 strings
    - Empty strings
    """
    assert is_equal_utf_8(b"hello", "hello") is True
    assert is_equal_utf_8("café".encode("utf-8"), "café") is True
    assert is_equal_utf_8(b"", "") is True


def test_is_equal_utf_8_not_matching():
    """
    Test is_equal_utf_8 with non-matching bytes and strings.

    Flow:
    1. Compare UTF-8 bytes with different string
    2. Verify equality check returns False

    Edge cases tested:
    - Different content
    - Incomplete multibyte sequences
    - Invalid UTF-8 bytes
    """
    assert is_equal_utf_8(b"hello", "world") is False
    assert is_equal_utf_8(b"\xc3", "é") is False  # Incomplete sequence
    assert is_equal_utf_8(b"\xff\xfe", "test") is False  # Invalid UTF-8
