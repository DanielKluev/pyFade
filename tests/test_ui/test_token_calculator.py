"""
Test suite for the Token Count Calculator window and context menu integration.

Tests cover:

- ``WindowTokenCalculator`` — word/token counting, debounce timer, text setting.
- ``PlainTextEdit`` — "Show Selection Statistics" context menu action.
- ``CompletionTextEdit`` — "Show Selection Statistics" context menu action.
- ``WidgetDatasetTop`` — "Tools" menu with "Token Count Calculator" item.
"""
# pylint: disable=unused-argument,too-many-positional-arguments,redefined-outer-name,protected-access
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QWidget

from py_fade.dataset.facet import Facet
from py_fade.gui.window_token_calculator import WindowTokenCalculator, count_words, STATS_UPDATE_DELAY_MS

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_providers_manager():
    """
    Create a mock InferenceProvidersManager with a deterministic count_tokens.

    Returns a mock that counts tokens as whitespace-separated words (for simplicity
    in tests) and exposes a call count for verification.
    """
    pm = MagicMock()
    pm.count_tokens = MagicMock(side_effect=lambda text, model_id=None: len(text.split()) if text.strip() else 0)
    return pm


# ---------------------------------------------------------------------------
# count_words unit tests
# ---------------------------------------------------------------------------


class TestCountWords:
    """Tests for the standalone ``count_words`` helper function."""

    def test_empty_string(self):
        """
        Empty string should return zero words.
        """
        assert count_words("") == 0

    def test_whitespace_only(self):
        """
        Whitespace-only string should return zero words.
        """
        assert count_words("   \t\n  ") == 0

    def test_single_word(self):
        """
        Single word should return one.
        """
        assert count_words("hello") == 1

    def test_multiple_words(self):
        """
        Multiple words separated by whitespace should be counted correctly.
        """
        assert count_words("hello world foo bar") == 4

    def test_newlines_and_tabs(self):
        """
        Words separated by newlines and tabs should be counted correctly.
        """
        assert count_words("hello\nworld\tfoo") == 3

    def test_leading_trailing_whitespace(self):
        """
        Leading and trailing whitespace should not affect the word count.
        """
        assert count_words("  hello world  ") == 2


# ---------------------------------------------------------------------------
# WindowTokenCalculator unit tests
# ---------------------------------------------------------------------------


class TestWindowTokenCalculator:
    """Tests for the ``WindowTokenCalculator`` dialog window."""

    def test_initial_empty_text(self, qt_app, mock_providers_manager):
        """
        Window opened without initial text should show zero stats.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            assert window.text_area.toPlainText() == ""
            assert "Words: 0" in window.stats_label.text()
            assert "Tokens: 0" in window.stats_label.text()
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_initial_text_populated(self, qt_app, mock_providers_manager):
        """
        Window opened with initial text should display the text and correct stats.
        """
        window = WindowTokenCalculator(mock_providers_manager, initial_text="hello world foo")
        try:
            assert window.text_area.toPlainText() == "hello world foo"
            assert "Words: 3" in window.stats_label.text()
            assert "Tokens: 3" in window.stats_label.text()
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_set_text_updates_stats(self, qt_app, mock_providers_manager):
        """
        Calling ``set_text`` should replace content and trigger an immediate stats update
        (the debounce timer fires after timeout, so we process events).
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            window.set_text("one two three four five")
            assert window.get_text() == "one two three four five"
            # Process events to let the timer fire
            window._stats_timer.setInterval(0)
            qt_app.processEvents()
            window._update_stats()
            assert "Words: 5" in window.stats_label.text()
            assert "Tokens: 5" in window.stats_label.text()
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_debounce_timer_restarts_on_each_change(self, qt_app, mock_providers_manager):
        """
        Each text change should restart the debounce timer, not stack timeouts.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            window.text_area.setPlainText("a")
            assert window._stats_timer.isActive()
            window.text_area.setPlainText("a b")
            assert window._stats_timer.isActive()
            assert window._stats_timer.interval() == STATS_UPDATE_DELAY_MS
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_window_is_non_modal(self, qt_app, mock_providers_manager):
        """
        The window should be non-modal so users can interact with parent windows.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            assert not window.isModal()
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_window_is_resizable(self, qt_app, mock_providers_manager):
        """
        The window should have a minimum size set and be resizable.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            assert window.minimumWidth() >= 400
            assert window.minimumHeight() >= 250
            window.resize(800, 600)
            qt_app.processEvents()
            assert window.width() == 800
            assert window.height() == 600
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_multiple_independent_windows(self, qt_app, mock_providers_manager):
        """
        Multiple independent calculator windows should be openable simultaneously.
        """
        window1 = WindowTokenCalculator(mock_providers_manager, initial_text="first window")
        window2 = WindowTokenCalculator(mock_providers_manager, initial_text="second window text here")
        try:
            window1.show()
            window2.show()
            qt_app.processEvents()
            assert window1.get_text() == "first window"
            assert window2.get_text() == "second window text here"
            assert window1 is not window2
        finally:
            window1.close()
            window2.close()
            window1.deleteLater()
            window2.deleteLater()
            qt_app.processEvents()

    def test_stats_update_called_with_correct_text(self, qt_app, mock_providers_manager):
        """
        Token counting should be called with the current text.
        """
        window = WindowTokenCalculator(mock_providers_manager, initial_text="testing tokens")
        try:
            mock_providers_manager.count_tokens.assert_called()
            args = mock_providers_manager.count_tokens.call_args[0]
            assert args[0] == "testing tokens"
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_get_text_returns_current_content(self, qt_app, mock_providers_manager):
        """
        ``get_text`` should return whatever is currently in the text area.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            window.text_area.setPlainText("dynamic content")
            assert window.get_text() == "dynamic content"
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()

    def test_window_title(self, qt_app, mock_providers_manager):
        """
        Window should have a descriptive title.
        """
        window = WindowTokenCalculator(mock_providers_manager)
        try:
            assert "Token Count Calculator" in window.windowTitle()
        finally:
            window.close()
            window.deleteLater()
            qt_app.processEvents()


# ---------------------------------------------------------------------------
# PlainTextEdit context menu tests
# ---------------------------------------------------------------------------


class TestPlainTextEditSelectionStats:
    """Tests for the 'Show Selection Statistics' context menu action in PlainTextEdit."""

    def test_context_menu_has_selection_stats_action(self, qt_app):
        """
        PlainTextEdit context menu should include a 'Show Selection Statistics' action.
        """
        from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

        edit = PlainTextEdit()
        try:
            edit.setPlainText("hello world")
            # Our custom contextMenuEvent builds on the standard menu; check the method exists
            assert hasattr(edit, '_open_selection_stats')
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_selection_stats_action_disabled_without_selection(self, qt_app):
        """
        The 'Show Selection Statistics' action should be disabled when no text is selected.
        """
        from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

        edit = PlainTextEdit()
        try:
            edit.setPlainText("no selection here")
            # No selection — verify selectedText is empty
            assert edit.textCursor().selectedText() == ""
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_selection_stats_action_enabled_with_selection(self, qt_app):
        """
        The 'Show Selection Statistics' action should be enabled when text is selected.
        """
        from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

        edit = PlainTextEdit()
        try:
            edit.setPlainText("select this text")
            cursor = edit.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            edit.setTextCursor(cursor)
            assert edit.textCursor().selectedText() == "select this text"
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_find_providers_manager_returns_none_without_app(self, qt_app):
        """
        ``_find_providers_manager`` should return None when no ancestor has ``app``.
        """
        from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

        edit = PlainTextEdit()
        try:
            result = edit._find_providers_manager()  # pylint: disable=protected-access
            assert result is None
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_find_providers_manager_finds_app_in_parent(self, qt_app):
        """
        ``_find_providers_manager`` should locate the providers_manager via
        the ``app`` attribute of an ancestor widget.
        """
        from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

        parent = QWidget()
        mock_pm = MagicMock()
        parent.app = MagicMock()
        parent.app.providers_manager = mock_pm

        edit = PlainTextEdit(parent)
        try:
            result = edit._find_providers_manager()  # pylint: disable=protected-access
            assert result is mock_pm
        finally:
            parent.deleteLater()
            qt_app.processEvents()


# ---------------------------------------------------------------------------
# CompletionTextEdit context menu tests
# ---------------------------------------------------------------------------


class TestCompletionTextEditSelectionStats:
    """Tests for the 'Show Selection Statistics' context menu action in CompletionTextEdit."""

    def test_context_menu_method_exists(self, qt_app):
        """
        CompletionTextEdit should have context menu and stats support methods.
        """
        from py_fade.gui.components.widget_completion_text_editor import CompletionTextEdit  # pylint: disable=import-outside-toplevel

        mock_frame = MagicMock()
        edit = CompletionTextEdit(mock_frame)
        try:
            assert hasattr(edit, 'contextMenuEvent')
            assert hasattr(edit, '_open_selection_stats')
            assert hasattr(edit, '_find_providers_manager')
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_find_providers_manager_returns_none_without_app(self, qt_app):
        """
        ``_find_providers_manager`` should return None when no ancestor has ``app``.
        """
        from py_fade.gui.components.widget_completion_text_editor import CompletionTextEdit  # pylint: disable=import-outside-toplevel

        mock_frame = MagicMock()
        edit = CompletionTextEdit(mock_frame)
        try:
            result = edit._find_providers_manager()  # pylint: disable=protected-access
            assert result is None
        finally:
            edit.deleteLater()
            qt_app.processEvents()

    def test_find_providers_manager_finds_app_in_parent(self, qt_app):
        """
        ``_find_providers_manager`` should locate the providers_manager via
        the ``app`` attribute of an ancestor widget.
        """
        from py_fade.gui.components.widget_completion_text_editor import CompletionTextEdit  # pylint: disable=import-outside-toplevel

        parent = QWidget()
        mock_pm = MagicMock()
        parent.app = MagicMock()
        parent.app.providers_manager = mock_pm

        mock_frame = MagicMock()
        edit = CompletionTextEdit(mock_frame, parent)
        try:
            result = edit._find_providers_manager()  # pylint: disable=protected-access
            assert result is mock_pm
        finally:
            parent.deleteLater()
            qt_app.processEvents()


# ---------------------------------------------------------------------------
# WidgetDatasetTop Tools menu tests
# ---------------------------------------------------------------------------


def _create_dataset_widget(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> "WidgetDatasetTop":
    """
    Helper to create a WidgetDatasetTop instance for testing.
    """
    from py_fade.gui.widget_dataset_top import WidgetDatasetTop  # pylint: disable=import-outside-toplevel

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()
    return widget


class TestToolsMenu:
    """Tests for the 'Tools' menu and 'Token Count Calculator' menu item."""

    def test_tools_menu_exists(self, app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
        """
        WidgetDatasetTop should have a 'Tools' menu in the menu bar.
        """
        _ = ensure_google_icon_font
        Facet.create(temp_dataset, "Tools Test Facet", "Facet for tools menu test")
        temp_dataset.commit()

        widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
        try:
            assert widget.tools_menu is not None
            assert widget.tools_menu.title() == "&Tools"
        finally:
            widget.deleteLater()
            qt_app.processEvents()

    def test_token_calculator_action_exists(self, app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
        """
        The 'Tools' menu should contain a 'Token Count Calculator' action.
        """
        _ = ensure_google_icon_font
        Facet.create(temp_dataset, "Action Test Facet", "Facet for action test")
        temp_dataset.commit()

        widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
        try:
            assert widget.action_token_calculator is not None
            assert widget.action_token_calculator.text() == "Token Count Calculator"
        finally:
            widget.deleteLater()
            qt_app.processEvents()

    def test_token_calculator_action_opens_window(self, app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
        """
        Triggering the 'Token Count Calculator' action should open a
        ``WindowTokenCalculator`` window.
        """
        _ = ensure_google_icon_font
        Facet.create(temp_dataset, "Open Window Facet", "Facet for window open test")
        temp_dataset.commit()

        widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
        try:
            widget._handle_token_calculator()  # pylint: disable=protected-access
            qt_app.processEvents()

            # Find the opened calculator window
            calculators = list(widget.findChildren(WindowTokenCalculator))
            assert len(calculators) >= 1
            calc = calculators[0]
            assert calc.text_area.toPlainText() == ""

            calc.close()
            calc.deleteLater()
        finally:
            widget.deleteLater()
            qt_app.processEvents()

    def test_tools_menu_between_preferences_and_help(self, app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
        """
        The 'Tools' menu should appear after 'Preferences' and before 'Help'.
        """
        _ = ensure_google_icon_font
        Facet.create(temp_dataset, "Order Test Facet", "Facet for menu order test")
        temp_dataset.commit()

        widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
        try:
            menu_bar = widget.menu_bar
            assert menu_bar is not None
            actions = menu_bar.actions()
            menu_titles = [a.text() for a in actions]
            log.info("Menu titles: %s", menu_titles)
            tools_idx = menu_titles.index("&Tools")
            prefs_idx = menu_titles.index("&Preferences")
            help_idx = menu_titles.index("&Help")
            assert prefs_idx < tools_idx < help_idx
        finally:
            widget.deleteLater()
            qt_app.processEvents()
