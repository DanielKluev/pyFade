"""
Test Widget Plain Text Edit test module.

Tests for PlainTextEdit component that enforces plain text input only,
rejecting rich formatted content from copy-paste operations.
"""
import pytest
from PyQt6.QtCore import QMimeData

from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit
from py_fade.providers.flat_prefix_template import (
    FLAT_PREFIX_ASSISTANT,
    FLAT_PREFIX_SYSTEM,
    FLAT_PREFIX_USER,
)


@pytest.fixture
def plain_text_edit(qtbot):
    """Create a PlainTextEdit instance for testing."""
    widget = PlainTextEdit()
    qtbot.addWidget(widget)
    return widget


def test_plain_text_edit_accepts_plain_text(plain_text_edit):  # pylint: disable=redefined-outer-name
    """
    Test that PlainTextEdit accepts and displays plain text correctly.
    
    Verifies basic functionality of the PlainTextEdit with plain text input.
    """
    prompt_text = "This is a simple plain text prompt"
    plain_text_edit.setPlainText(prompt_text)

    # Verify the text was set correctly
    assert plain_text_edit.toPlainText() == prompt_text


def test_plain_text_edit_rejects_rich_text_via_mime_data(plain_text_edit):  # pylint: disable=redefined-outer-name
    """
    Test that PlainTextEdit rejects rich formatted text during paste operations.
    
    Simulates copying rich HTML content (like from a web page) and verifies
    that only plain text is pasted into the editor.
    """
    # Create rich HTML content similar to what might be copied from a web page
    rich_html = """
    <html>
    <head><style>p { color: red; font-weight: bold; }</style></head>
    <body>
    <p style="color: blue; font-size: 18px;">This is <strong>bold</strong> and <em>italic</em> text</p>
    <div style="background-color: yellow;">With background colors</div>
    </body>
    </html>
    """

    expected_plain_text = "This is bold and italic text\nWith background colors"

    # Create a QMimeData object with rich text (simulating copy from web page)
    mime_data = QMimeData()
    mime_data.setHtml(rich_html)
    mime_data.setText(expected_plain_text)

    # Clear the editor and insert mime data
    plain_text_edit.clear()
    plain_text_edit.insertFromMimeData(mime_data)

    # Verify that only plain text was pasted (no rich formatting)
    result_text = plain_text_edit.toPlainText().strip()
    result_html = plain_text_edit.toHtml()

    # The result should be plain text without formatting
    assert result_text == expected_plain_text

    # The HTML should not contain rich formatting elements from the original input
    # Note: QTextEdit generates basic HTML wrapper with default styles, but it shouldn't
    # contain the rich formatting from the pasted input (blue color, large font, etc.)
    assert "color: blue" not in result_html
    assert "font-size: 18px" not in result_html
    assert "background-color: yellow" not in result_html
    assert "<strong>" not in result_html
    assert "<em>" not in result_html


def test_plain_text_edit_set_html_converts_to_plain_text(plain_text_edit):  # pylint: disable=redefined-outer-name
    """
    Test that setHtml method converts rich content to plain text.
    
    Verifies that even programmatic attempts to set HTML are converted
    to plain text only.
    """
    rich_html = '<p style="color: red; font-weight: bold;">Rich <strong>formatted</strong> text</p>'
    expected_plain = "Rich formatted text"

    plain_text_edit.setHtml(rich_html)

    result_text = plain_text_edit.toPlainText().strip()
    assert result_text == expected_plain


def test_plain_text_edit_preserves_programmed_formatting(plain_text_edit):  # pylint: disable=redefined-outer-name
    """
    Test that PlainTextEdit preserves programmed formatting markers.
    
    Verifies that the editor allows programmed formatting like
    flat prefix templates (FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, etc.)
    but rejects external rich formatting.
    """
    # Create text with programmed formatting markers
    prompt_with_markers = f"""
{FLAT_PREFIX_SYSTEM}
You are a helpful assistant.

{FLAT_PREFIX_USER}
What is Python?

{FLAT_PREFIX_ASSISTANT}
Python is a programming language.
"""

    plain_text_edit.setPlainText(prompt_with_markers)
    result_text = plain_text_edit.toPlainText()

    # Verify that programmed formatting markers are preserved
    assert FLAT_PREFIX_SYSTEM in result_text
    assert FLAT_PREFIX_USER in result_text
    assert FLAT_PREFIX_ASSISTANT in result_text
    assert "You are a helpful assistant." in result_text
    assert "What is Python?" in result_text
    assert "Python is a programming language." in result_text


def test_plain_text_edit_handles_mime_data_without_text(plain_text_edit):  # pylint: disable=redefined-outer-name
    """
    Test that PlainTextEdit handles mime data that contains no text gracefully.
    
    Verifies that the widget doesn't crash when mime data with no text
    content is provided.
    """
    # Create mime data with no text
    mime_data = QMimeData()
    mime_data.setImageData(b"fake_image_data")  # Some non-text data

    original_text = "Original content"
    plain_text_edit.setPlainText(original_text)

    # This should not change the content since there's no text in mime data
    plain_text_edit.insertFromMimeData(mime_data)

    # Content should remain unchanged
    assert plain_text_edit.toPlainText() == original_text
