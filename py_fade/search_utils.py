"""
Utilities for search and filtering operations.
"""


def parse_search_value_as_int(search_value: str) -> tuple[int | None, bool]:
    """
    Parse a search value string and determine if it's a valid integer.

    Args:
        search_value: The search string to parse

    Returns:
        A tuple of (search_id, is_valid_id) where:
        - search_id is the integer value if valid, None otherwise
        - is_valid_id is True if the value was successfully parsed as an integer
    """
    try:
        search_id = int(search_value)
        is_valid_id = True
    except ValueError:
        search_id = None
        is_valid_id = False

    return search_id, is_valid_id
