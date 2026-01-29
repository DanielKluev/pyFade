"""
Test tab title shortening functionality.

This module tests the tab title shortening logic that is applied when tab titles
are too long (more than 8 words).
"""

from py_fade.gui.gui_helpers import shorten_tab_title


def test_short_title_unchanged():
    """
    Test that short titles (8 words or less) are not modified.
    
    Verifies that titles with 8 or fewer words are returned unchanged.
    """
    # Test titles with fewer than 8 words
    assert shorten_tab_title("S: Simple title") == "S: Simple title"
    assert shorten_tab_title("F: One two three") == "F: One two three"
    assert shorten_tab_title("T: One two three four five six") == "T: One two three four five six"

    # Test title with exactly 8 words
    assert shorten_tab_title("S: One two three four five six seven") == "S: One two three four five six seven"


def test_long_title_shortened():
    """
    Test that long titles (more than 8 words) are properly shortened.
    
    Verifies that titles with more than 8 words are shortened to first 6 words,
    followed by "...", followed by last 2 words.
    """
    # Test title with 9 words (should be shortened)
    title = "S: One two three four five six seven eight"
    expected = "S: One two three four five ... seven eight"
    assert shorten_tab_title(title) == expected

    # Test title with 10 words
    title = "S: One two three four five six seven eight nine"
    expected = "S: One two three four five ... eight nine"
    assert shorten_tab_title(title) == expected

    # Test title with many words
    title = "S: This is a very very very long sample title that needs shortening"
    expected = "S: This is a very very ... needs shortening"
    assert shorten_tab_title(title) == expected


def test_different_prefixes():
    """
    Test that shortening works correctly with different tab type prefixes.
    
    Verifies that the shortening logic works for all tab types: Sample (S:),
    Facet (F:), Tag (T:), Sample Filter (SF:), and Export Template (X:).
    """
    # Sample prefix
    title = "S: Word one two three four five six seven eight"
    expected = "S: Word one two three four ... seven eight"
    assert shorten_tab_title(title) == expected

    # Facet prefix
    title = "F: Word one two three four five six seven eight"
    expected = "F: Word one two three four ... seven eight"
    assert shorten_tab_title(title) == expected

    # Tag prefix
    title = "T: Word one two three four five six seven eight"
    expected = "T: Word one two three four ... seven eight"
    assert shorten_tab_title(title) == expected

    # Sample Filter prefix
    title = "SF: Word one two three four five six seven eight"
    expected = "SF: Word one two three four ... seven eight"
    assert shorten_tab_title(title) == expected

    # Export Template prefix
    title = "X: Word one two three four five six seven eight"
    expected = "X: Word one two three four ... seven eight"
    assert shorten_tab_title(title) == expected


def test_no_prefix():
    """
    Test that shortening works for titles without standard prefixes.
    
    Verifies that the shortening logic works for titles like "Overview" or
    "New Sample" that don't have the standard type prefix.
    """
    # Overview tab (no prefix)
    assert shorten_tab_title("Overview") == "Overview"

    # New item tabs (no prefix, short)
    assert shorten_tab_title("New Sample") == "New Sample"
    assert shorten_tab_title("New Facet") == "New Facet"

    # Long title without prefix (11 words)
    title = "This is a very long title without any prefix at all"
    expected = "This is a very long title ... at all"
    assert shorten_tab_title(title) == expected


def test_edge_cases():
    """
    Test edge cases for tab title shortening.
    
    Verifies correct behavior for empty strings, single words, and titles
    with unusual spacing.
    """
    # Empty string
    assert shorten_tab_title("") == ""

    # Single word
    assert shorten_tab_title("SingleWord") == "SingleWord"

    # Multiple spaces between words (should treat as single separator)
    title = "S:  Word  one  two  three  four  five  six  seven  eight  nine"
    # Split by whitespace and filter empty strings
    words = title.split()
    assert len(words) == 11  # S:, Word, one, ..., nine (11 words total)
    result = shorten_tab_title(title)
    # Should still be shortened
    assert "..." in result


def test_special_characters():
    """
    Test that shortening preserves special characters in words.
    
    Verifies that special characters, punctuation, and unicode characters
    are preserved correctly in shortened titles.
    """
    # Title with special characters
    title = "S: Sample-1 with_underscore and (parentheses) plus #hashtag and @mention more words here"
    expected = "S: Sample-1 with_underscore and (parentheses) plus ... words here"
    assert shorten_tab_title(title) == expected

    # Title with unicode characters
    title = "S: Über façade naïve résumé café one two three four"
    expected = "S: Über façade naïve résumé café ... three four"
    assert shorten_tab_title(title) == expected


def test_realistic_sample_titles():
    """
    Test realistic sample titles from actual usage.
    
    Verifies that the shortening works correctly with realistic sample titles
    that might appear in the application.
    """
    # Realistic long sample title (14 words)
    title = "S: Explain the concept of quantum entanglement in simple terms for a beginner"
    expected = "S: Explain the concept of quantum ... a beginner"
    assert shorten_tab_title(title) == expected

    # Another realistic example (11 words)
    title = "F: System prompt for creative writing assistant with detailed personality traits"
    expected = "F: System prompt for creative writing ... personality traits"
    assert shorten_tab_title(title) == expected

    # Short realistic title (unchanged)
    title = "T: Technical Documentation"
    assert shorten_tab_title(title) == "T: Technical Documentation"
