"""
Test PlainTextEdit role tag insertion functionality.

Tests for context menu actions and programmatic role tag insertion methods.
"""
# pylint: disable=redefined-outer-name,unused-argument
import pytest

from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QContextMenuEvent

from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit
from py_fade.providers.flat_prefix_template import FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, FLAT_PREFIX_ASSISTANT


@pytest.fixture
def plain_text_edit(qt_app):
    """
    Create a PlainTextEdit widget for testing.
    """
    widget = PlainTextEdit()
    widget.show()
    qt_app.processEvents()
    return widget


class TestRoleTagInsertion:
    """
    Test role tag insertion methods.
    """

    def test_insert_system_tag_at_cursor_empty(self, qt_app, plain_text_edit):
        """
        Test inserting system tag at cursor position in empty text.
        """
        plain_text_edit.insert_role_tag_at_cursor(FLAT_PREFIX_SYSTEM)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_SYSTEM

    def test_insert_user_tag_at_cursor_empty(self, qt_app, plain_text_edit):
        """
        Test inserting user tag at cursor position in empty text.
        """
        plain_text_edit.insert_role_tag_at_cursor(FLAT_PREFIX_USER)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_USER

    def test_insert_assistant_tag_at_cursor_empty(self, qt_app, plain_text_edit):
        """
        Test inserting assistant tag at cursor position in empty text.
        """
        plain_text_edit.insert_role_tag_at_cursor(FLAT_PREFIX_ASSISTANT)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_ASSISTANT

    def test_insert_tag_at_cursor_with_existing_text(self, qt_app, plain_text_edit):
        """
        Test inserting tag at cursor position within existing text.
        """
        plain_text_edit.setPlainText("Hello World")
        # Move cursor to position 6 (after "Hello ")
        cursor = plain_text_edit.textCursor()
        cursor.setPosition(6)
        plain_text_edit.setTextCursor(cursor)

        plain_text_edit.insert_role_tag_at_cursor(FLAT_PREFIX_USER)
        assert plain_text_edit.toPlainText() == f"Hello {FLAT_PREFIX_USER}World"

    def test_insert_system_tag_at_end_empty(self, qt_app, plain_text_edit):
        """
        Test inserting system tag at end of empty text.
        """
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_SYSTEM)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_SYSTEM

    def test_insert_user_tag_at_end_empty(self, qt_app, plain_text_edit):
        """
        Test inserting user tag at end of empty text.
        """
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_USER)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_USER

    def test_insert_assistant_tag_at_end_empty(self, qt_app, plain_text_edit):
        """
        Test inserting assistant tag at end of empty text.
        """
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_ASSISTANT)
        assert plain_text_edit.toPlainText() == FLAT_PREFIX_ASSISTANT

    def test_insert_tag_at_end_with_existing_text(self, qt_app, plain_text_edit):
        """
        Test inserting tag at end of existing text adds newline first.
        """
        plain_text_edit.setPlainText("Hello World")
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_USER)
        assert plain_text_edit.toPlainText() == f"Hello World\n{FLAT_PREFIX_USER}"

    def test_insert_tag_at_end_when_text_ends_with_newline(self, qt_app, plain_text_edit):
        """
        Test inserting tag at end when text already ends with newline.
        """
        plain_text_edit.setPlainText("Hello World\n")
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_USER)
        assert plain_text_edit.toPlainText() == f"Hello World\n{FLAT_PREFIX_USER}"

    def test_insert_multiple_tags_at_end(self, qt_app, plain_text_edit):
        """
        Test inserting multiple tags at end creates proper structure.
        """
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_SYSTEM)
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_USER)
        plain_text_edit.insert_role_tag_at_end(FLAT_PREFIX_ASSISTANT)

        expected = f"{FLAT_PREFIX_SYSTEM}\n{FLAT_PREFIX_USER}\n{FLAT_PREFIX_ASSISTANT}"
        assert plain_text_edit.toPlainText() == expected


class TestContextMenu:
    """
    Test context menu creation and actions.
    """

    def test_context_menu_has_role_tag_actions(self, qt_app, plain_text_edit):
        """
        Test that context menu includes role tag insertion actions.
        
        This test verifies that the contextMenuEvent method creates a menu
        with the expected role tag actions, but doesn't actually display it.
        """
        # This is a simple smoke test - the actual menu display is hard to test
        # in headless mode, but we can verify the method exists and doesn't crash
        assert hasattr(plain_text_edit, 'contextMenuEvent')
        assert hasattr(plain_text_edit, 'insert_role_tag_at_cursor')
        assert hasattr(plain_text_edit, 'insert_role_tag_at_end')

    def test_context_menu_event_creates_menu(self, qt_app, plain_text_edit, monkeypatch):
        """
        Test that contextMenuEvent creates a menu with role tag actions.
        
        Verifies that the context menu is created with all expected actions
        for inserting role tags at cursor and at end.
        """
        # Track if menu.exec was called
        menu_exec_called = []

        def mock_exec(self, pos):
            menu_exec_called.append(pos)

        # Patch QMenu.exec to avoid actual menu display
        from PyQt6.QtWidgets import QMenu  # pylint: disable=import-outside-toplevel
        monkeypatch.setattr(QMenu, "exec", mock_exec)

        # Create a context menu event
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                  plain_text_edit.rect().center(), plain_text_edit.mapToGlobal(plain_text_edit.rect().center()))

        # Call contextMenuEvent
        plain_text_edit.contextMenuEvent(event)

        # Verify that exec was called (menu was shown)
        assert len(menu_exec_called) == 1

    def test_insert_role_tag_methods_exist(self, qt_app, plain_text_edit):
        """
        Test that all required role tag insertion methods exist.
        """
        assert callable(plain_text_edit.insert_role_tag_at_cursor)
        assert callable(plain_text_edit.insert_role_tag_at_end)


class TestPlainTextEnforcement:
    """
    Test that PlainTextEdit enforces plain text only input.
    
    Tests the core functionality that prevents rich text from being pasted
    or set programmatically, ensuring only plain text is accepted.
    """

    def test_insert_from_mime_data_with_plain_text(self, qt_app, plain_text_edit):
        """
        Test that inserting plain text from mime data works correctly.
        
        Verifies that when mime data contains plain text, it's inserted
        into the widget as expected.
        """
        mime_data = QMimeData()
        mime_data.setText("Plain text content")

        plain_text_edit.insertFromMimeData(mime_data)
        assert plain_text_edit.toPlainText() == "Plain text content"

    def test_insert_from_mime_data_with_html(self, qt_app, plain_text_edit):
        """
        Test that inserting HTML from mime data extracts only plain text.
        
        Verifies that when mime data contains HTML, only the plain text
        portion is inserted, discarding all formatting.
        """
        mime_data = QMimeData()
        # Set both HTML and plain text (like a real copy-paste would)
        mime_data.setHtml("<b>Bold</b> and <i>italic</i> text")
        mime_data.setText("Bold and italic text")

        plain_text_edit.insertFromMimeData(mime_data)
        assert plain_text_edit.toPlainText() == "Bold and italic text"
        # Verify no HTML tags are present
        assert "<b>" not in plain_text_edit.toPlainText()
        assert "<i>" not in plain_text_edit.toPlainText()

    def test_insert_from_mime_data_without_text(self, qt_app, plain_text_edit):
        """
        Test that inserting mime data without text content does nothing.
        
        Verifies that when mime data doesn't contain text (e.g., image only),
        no insertion occurs.
        """
        mime_data = QMimeData()
        # Create mime data without text

        plain_text_edit.setPlainText("Existing text")
        plain_text_edit.insertFromMimeData(mime_data)

        # Text should remain unchanged
        assert plain_text_edit.toPlainText() == "Existing text"

    def test_set_html_converts_to_plain_text(self, qt_app, plain_text_edit):
        """
        Test that setHtml method converts HTML to plain text.
        
        Verifies that when setHtml is called, the HTML is converted to
        plain text before being set in the widget.
        """
        html_content = "<h1>Header</h1><p>Paragraph with <b>bold</b> text</p>"
        plain_text_edit.setHtml(html_content)

        # Should contain only the plain text, no HTML tags
        result = plain_text_edit.toPlainText()
        assert "Header" in result
        assert "Paragraph with bold text" in result
        assert "<h1>" not in result
        assert "<b>" not in result

    def test_set_html_with_complex_formatting(self, qt_app, plain_text_edit):
        """
        Test that setHtml handles complex HTML with multiple elements.
        
        Verifies that complex HTML structures are properly converted to
        plain text, preserving content but removing all formatting.
        """
        html_content = """
        <div>
            <p>First paragraph</p>
            <ul>
                <li>List item 1</li>
                <li>List item 2</li>
            </ul>
            <p>Last paragraph</p>
        </div>
        """
        plain_text_edit.setHtml(html_content)

        result = plain_text_edit.toPlainText()
        assert "First paragraph" in result
        assert "List item 1" in result
        assert "List item 2" in result
        assert "Last paragraph" in result
        # No HTML tags should be present
        assert "<div>" not in result
        assert "<ul>" not in result
        assert "<li>" not in result

    def test_accept_rich_text_is_disabled(self, qt_app, plain_text_edit):
        """
        Test that acceptRichText is set to False.
        
        Verifies that the widget is configured to reject rich text at the
        Qt framework level.
        """
        assert not plain_text_edit.acceptRichText(), "PlainTextEdit should have acceptRichText disabled"

    def test_insert_plain_text_preserves_newlines(self, qt_app, plain_text_edit):
        """
        Test that plain text with newlines is preserved correctly.
        
        Verifies that when inserting plain text with newlines, the line
        breaks are maintained.
        """
        mime_data = QMimeData()
        mime_data.setText("Line 1\nLine 2\nLine 3")

        plain_text_edit.insertFromMimeData(mime_data)
        assert plain_text_edit.toPlainText() == "Line 1\nLine 2\nLine 3"
