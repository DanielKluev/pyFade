"""
Test WidgetSample role tag button functionality.

Tests for the S, U, A buttons that insert role tags at the end of the prompt.
"""
# pylint: disable=redefined-outer-name,unused-argument
from unittest.mock import patch

import pytest

from py_fade.gui.widget_sample import WidgetSample
from py_fade.providers.flat_prefix_template import FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, FLAT_PREFIX_ASSISTANT


@pytest.fixture
def widget_sample(qt_app, app_with_dataset, ensure_google_icon_font):
    """
    Create a WidgetSample for testing.
    """
    _ = ensure_google_icon_font
    widget = WidgetSample(parent=None, app=app_with_dataset, sample=None)
    widget.show()
    qt_app.processEvents()
    return widget


class TestRoleTagButtons:
    """
    Test role tag insertion buttons in WidgetSample.
    """

    def test_role_tag_buttons_exist(self, qt_app, widget_sample):
        """
        Test that role tag buttons exist in the widget.
        """
        assert hasattr(widget_sample, 'system_tag_button')
        assert hasattr(widget_sample, 'user_tag_button')
        assert hasattr(widget_sample, 'assistant_tag_button')

    def test_system_button_inserts_tag_at_beginning_empty(self, qt_app, widget_sample):
        """
        Test that system button inserts tag at beginning of empty text.
        """
        widget_sample.prompt_area.clear()
        widget_sample.insert_system_tag()
        assert widget_sample.prompt_area.toPlainText() == FLAT_PREFIX_SYSTEM

    def test_system_button_inserts_tag_at_beginning_with_text(self, qt_app, widget_sample):
        """
        Test that system button inserts tag at beginning with existing text.
        """
        widget_sample.prompt_area.setPlainText("Existing text")
        widget_sample.insert_system_tag()
        assert widget_sample.prompt_area.toPlainText() == f"{FLAT_PREFIX_SYSTEM}\nExisting text"

    def test_system_button_prevents_duplicate_system_tag(self, qt_app, widget_sample):
        """
        Test that system button prevents inserting duplicate system tags.
        """
        widget_sample.prompt_area.setPlainText(f"{FLAT_PREFIX_SYSTEM} System prompt")

        # Mock QMessageBox.warning to prevent actual dialog
        with patch('py_fade.gui.widget_sample.QMessageBox.warning') as mock_warning:
            widget_sample.insert_system_tag()

            # Verify warning was shown
            mock_warning.assert_called_once()

            # Verify text hasn't changed
            assert widget_sample.prompt_area.toPlainText() == f"{FLAT_PREFIX_SYSTEM} System prompt"

    def test_user_button_inserts_tag_at_end_empty(self, qt_app, widget_sample):
        """
        Test that user button inserts tag at end of empty text.
        """
        widget_sample.prompt_area.clear()
        widget_sample.insert_user_tag()
        assert widget_sample.prompt_area.toPlainText() == FLAT_PREFIX_USER

    def test_user_button_inserts_tag_at_end_with_text(self, qt_app, widget_sample):
        """
        Test that user button inserts tag at end with existing text.
        """
        widget_sample.prompt_area.setPlainText("Existing text")
        widget_sample.insert_user_tag()
        assert widget_sample.prompt_area.toPlainText() == f"Existing text\n{FLAT_PREFIX_USER}"

    def test_assistant_button_inserts_tag_at_end_empty(self, qt_app, widget_sample):
        """
        Test that assistant button inserts tag at end of empty text.
        """
        widget_sample.prompt_area.clear()
        widget_sample.insert_assistant_tag()
        assert widget_sample.prompt_area.toPlainText() == FLAT_PREFIX_ASSISTANT

    def test_assistant_button_inserts_tag_at_end_with_text(self, qt_app, widget_sample):
        """
        Test that assistant button inserts tag at end with existing text.
        """
        widget_sample.prompt_area.setPlainText("Existing text")
        widget_sample.insert_assistant_tag()
        assert widget_sample.prompt_area.toPlainText() == f"Existing text\n{FLAT_PREFIX_ASSISTANT}"

    def test_multiple_role_tags_insertion(self, qt_app, widget_sample):
        """
        Test inserting multiple role tags creates proper prompt structure.
        """
        widget_sample.prompt_area.clear()

        # Insert system tag
        widget_sample.insert_system_tag()

        # Insert user tag
        widget_sample.insert_user_tag()

        # Insert assistant tag
        widget_sample.insert_assistant_tag()

        expected = f"{FLAT_PREFIX_SYSTEM}\n{FLAT_PREFIX_USER}\n{FLAT_PREFIX_ASSISTANT}"
        assert widget_sample.prompt_area.toPlainText() == expected

    def test_system_tag_only_allowed_once(self, qt_app, widget_sample):
        """
        Test that system tag can only be inserted once.
        """
        widget_sample.prompt_area.clear()

        # First insertion should succeed
        widget_sample.insert_system_tag()
        assert FLAT_PREFIX_SYSTEM in widget_sample.prompt_area.toPlainText()

        # Second insertion should be prevented
        with patch('py_fade.gui.widget_sample.QMessageBox.warning') as mock_warning:
            widget_sample.insert_system_tag()
            mock_warning.assert_called_once()

            # Verify only one system tag exists
            text = widget_sample.prompt_area.toPlainText()
            assert text.count(FLAT_PREFIX_SYSTEM) == 1

    def test_user_and_assistant_tags_allowed_multiple_times(self, qt_app, widget_sample):
        """
        Test that user and assistant tags can be inserted multiple times.
        """
        widget_sample.prompt_area.clear()

        # Insert user tag twice
        widget_sample.insert_user_tag()
        widget_sample.insert_user_tag()

        # Insert assistant tag twice
        widget_sample.insert_assistant_tag()
        widget_sample.insert_assistant_tag()

        text = widget_sample.prompt_area.toPlainText()
        assert text.count(FLAT_PREFIX_USER) == 2
        assert text.count(FLAT_PREFIX_ASSISTANT) == 2


class TestRoleTagButtonConnections:
    """
    Test that buttons are properly connected to handlers.
    """

    def test_system_button_connected(self, qt_app, widget_sample):
        """
        Test that system button click triggers insert_system_tag.
        """
        widget_sample.prompt_area.clear()
        widget_sample.system_tag_button.click()
        qt_app.processEvents()
        assert FLAT_PREFIX_SYSTEM in widget_sample.prompt_area.toPlainText()

    def test_user_button_connected(self, qt_app, widget_sample):
        """
        Test that user button click triggers insert_user_tag.
        """
        widget_sample.prompt_area.clear()
        widget_sample.user_tag_button.click()
        qt_app.processEvents()
        assert FLAT_PREFIX_USER in widget_sample.prompt_area.toPlainText()

    def test_assistant_button_connected(self, qt_app, widget_sample):
        """
        Test that assistant button click triggers insert_assistant_tag.
        """
        widget_sample.prompt_area.clear()
        widget_sample.assistant_tag_button.click()
        qt_app.processEvents()
        assert FLAT_PREFIX_ASSISTANT in widget_sample.prompt_area.toPlainText()


class TestRoleTagButtonLocation:
    """
    Test that role tag buttons are in the prompt panel, below the prompt area.
    """

    def test_role_tag_buttons_in_prompt_panel(self, qt_app, widget_sample):
        """
        Test that role tag buttons are located in the prompt panel (with token counter), not the controls panel.
        """
        from PyQt6.QtWidgets import QFrame  # pylint: disable=import-outside-toplevel

        # Find the prompt frame (contains prompt_area and token_usage_label)
        prompt_frame = None
        frames = widget_sample.findChildren(QFrame)
        for frame in frames:
            if frame.__class__.__name__ == 'QSplitter':
                continue
            from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel
            text_edits = frame.findChildren(PlainTextEdit)
            if widget_sample.prompt_area in text_edits:
                prompt_frame = frame
                break

        assert prompt_frame is not None, "Prompt frame should be found"

        # Check that role tag buttons are children of the prompt frame
        from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon  # pylint: disable=import-outside-toplevel
        buttons_in_prompt = prompt_frame.findChildren(QPushButtonWithIcon)

        assert widget_sample.system_tag_button in buttons_in_prompt, "System tag button should be in prompt panel"
        assert widget_sample.user_tag_button in buttons_in_prompt, "User tag button should be in prompt panel"
        assert widget_sample.assistant_tag_button in buttons_in_prompt, "Assistant tag button should be in prompt panel"

    def test_role_tag_buttons_not_in_controls_area(self, qt_app, widget_sample):
        """
        Test that role tag buttons are NOT in the controls panel.
        """
        from PyQt6.QtWidgets import QFrame  # pylint: disable=import-outside-toplevel

        # Find the controls frame (contains id_field)
        controls_frame = None
        frames = widget_sample.findChildren(QFrame)
        for frame in frames:
            if frame.__class__.__name__ == 'QSplitter':
                continue
            from PyQt6.QtWidgets import QLineEdit  # pylint: disable=import-outside-toplevel
            lineedits = frame.findChildren(QLineEdit)
            if widget_sample.id_field in lineedits:
                controls_frame = frame
                break

        assert controls_frame is not None, "Controls frame should be found"

        # Check that role tag buttons are NOT children of the controls frame
        from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon  # pylint: disable=import-outside-toplevel
        buttons_in_controls = controls_frame.findChildren(QPushButtonWithIcon)

        assert widget_sample.system_tag_button not in buttons_in_controls, "System tag button should NOT be in controls panel"
        assert widget_sample.user_tag_button not in buttons_in_controls, "User tag button should NOT be in controls panel"
        assert widget_sample.assistant_tag_button not in buttons_in_controls, "Assistant tag button should NOT be in controls panel"
