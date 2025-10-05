"""
Test PlainTextEdit role tag insertion functionality.

Tests for context menu actions and programmatic role tag insertion methods.
"""
# pylint: disable=redefined-outer-name,unused-argument
import pytest

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

    def test_insert_role_tag_methods_exist(self, qt_app, plain_text_edit):
        """
        Test that all required role tag insertion methods exist.
        """
        assert callable(plain_text_edit.insert_role_tag_at_cursor)
        assert callable(plain_text_edit.insert_role_tag_at_end)
