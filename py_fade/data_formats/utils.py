"""
Data format handling utilities.
"""


def missing_bytes_utf_8(b: bytes) -> int:
    """
    Check if bytes `b` contain any invalid UTF-8 sequences.
    Returns number of bytes needed to complete the last character if incomplete,
    or 0 if valid UTF-8 or invalid sequence.
    """
    multibyte_fix = 0
    # Check last up to 3 bytes for multibyte sequence start
    for k, char in enumerate(b[-3:]):
        k = 3 - k
        for num, pattern in [(2, 192), (3, 224), (4, 240)]:
            # Bitwise AND check
            if num > k and pattern & char == pattern:
                multibyte_fix = num - k
    return multibyte_fix


def try_decode_utf_8(b: bytes) -> str | None:
    """
    Try to decode bytes `b` as UTF-8.
    Returns decoded string if successful, or None if decoding fails.
    """
    try:
        return b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def is_equal_utf_8(b: bytes, s: str) -> bool:
    """
    Check if bytes `b` equal string `s` when both are interpreted as UTF-8.
    """
    multibyte_fix = missing_bytes_utf_8(b)
    if multibyte_fix > 0:
        return False  # Incomplete multibyte sequence cannot match
    try:
        return b.decode("utf-8") == s
    except UnicodeDecodeError:
        return False
