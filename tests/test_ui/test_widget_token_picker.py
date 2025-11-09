"""
Test Token Picker test module.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QPushButton

from py_fade.gui.components.widget_token_picker import WidgetTokenPicker
from py_fade.data_formats.base_data_classes import SinglePositionTopLogprobs, SinglePositionToken
from tests.helpers.data_helpers import create_test_single_position_token


def test_token_picker_normalises_llm_logprob_objects(ensure_google_icon_font, qt_app):
    """Test that token picker properly normalizes SinglePositionToken objects."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("B", -1.2),
        create_test_single_position_token("A", -0.4),
        create_test_single_position_token("C", -3.1),
    ])

    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # In the new architecture, tokens are SinglePositionToken objects
        # The widget doesn't sort them - they should be pre-sorted by the caller
        assert [token.token_str for token in widget.tokens] == ["B", "A", "C"]
    finally:
        widget.deleteLater()


def test_token_picker_single_select_emits_selected_tokens(ensure_google_icon_font, qt_app):
    """Test that token picker in single-select mode emits selected tokens immediately."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("first", -0.1),
        create_test_single_position_token("second", -0.3),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    captured: list[list[SinglePositionToken]] = []
    widget.tokens_selected.connect(lambda payload: captured.append(list(payload)))

    try:
        first_button = widget.token_widgets[0]
        assert isinstance(first_button, QPushButton)
        first_button.click()
        qt_app.processEvents()

        assert captured
        # Now compare SinglePositionToken objects
        assert len(captured[-1]) == 1
        assert captured[-1][0].token_str == "first"
        assert captured[-1][0].logprob == -0.1

        # Selecting the second token should replace the selection.
        second_button = widget.token_widgets[1]
        assert isinstance(second_button, QPushButton)
        second_button.click()
        qt_app.processEvents()

        assert len(captured[-1]) == 1
        assert captured[-1][0].token_str == "second"
        assert captured[-1][0].logprob == -0.3
        assert not first_button.isChecked()
    finally:
        widget.deleteLater()


def test_token_picker_multi_select_requires_accept(ensure_google_icon_font, qt_app):
    """Test that token picker in multi-select mode requires explicit accept action."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("alpha", -0.5),
        create_test_single_position_token("beta", -0.2),
        create_test_single_position_token("gamma", -1.1),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=True)
    captured: list[list[SinglePositionToken]] = []
    widget.tokens_selected.connect(lambda payload: captured.append(list(payload)))

    try:
        first_checkbox = widget.token_widgets[0]
        second_checkbox = widget.token_widgets[1]
        assert isinstance(first_checkbox, QCheckBox)
        assert isinstance(second_checkbox, QCheckBox)

        first_checkbox.setChecked(True)
        second_checkbox.setChecked(True)
        qt_app.processEvents()

        widget.accept_button.click()
        qt_app.processEvents()

        assert captured
        # Compare SinglePositionToken objects
        assert len(captured[-1]) == 2
        token_strs = {t.token_str for t in captured[-1]}
        token_logprobs = {t.logprob for t in captured[-1]}
        assert token_strs == {"alpha", "beta"}
        assert token_logprobs == {-0.5, -0.2}

        widget.clear_selection()
        qt_app.processEvents()

        assert not widget.get_selected_tokens()
        assert not first_checkbox.isChecked()
        assert not second_checkbox.isChecked()
    finally:
        widget.deleteLater()


def test_token_picker_text_search_filter(ensure_google_icon_font, qt_app):
    """Test that text search filter works correctly."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token("world", -0.2),
        create_test_single_position_token("test", -0.3),
        create_test_single_position_token("help", -0.4),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Initially all 4 tokens should be visible
        assert len(widget.token_widgets) == 4

        # Filter by "hel" should show "hello" and "help"
        widget.search_input.setText("hel")
        qt_app.processEvents()
        assert len(widget.token_widgets) == 2
        visible_tokens = [w.text().split(" [")[0].replace("␣", " ") for w in widget.token_widgets]
        assert set(visible_tokens) == {"hello", "help"}

        # Filter by "world" should show only "world"
        widget.search_input.setText("world")
        qt_app.processEvents()
        assert len(widget.token_widgets) == 1
        assert widget.token_widgets[0].text().split(" [")[0] == "world"

        # Clear filter should show all tokens again
        widget.search_input.setText("")
        qt_app.processEvents()
        assert len(widget.token_widgets) == 4
    finally:
        widget.deleteLater()


def test_token_picker_latin_only_filter(ensure_google_icon_font, qt_app):
    """Test that Latin-only filter works correctly."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token("世界", -0.2),  # Chinese
        create_test_single_position_token("مرحبا", -0.3),  # Arabic
        create_test_single_position_token("test!", -0.4),
        create_test_single_position_token("Привет", -0.5),  # Cyrillic
        create_test_single_position_token(" space", -0.6),
        create_test_single_position_token("\n", -0.7),  # newline
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Initially all 7 tokens should be visible
        assert len(widget.token_widgets) == 7

        # Enable Latin-only filter
        widget.latin_only_button.click()
        qt_app.processEvents()

        # Should show only Latin tokens: "hello", "test!", " space", "\n"
        assert len(widget.token_widgets) == 4
        visible_tokens = [w.text().split(" [")[0].replace("␣", " ").replace("⏎", "\n") for w in widget.token_widgets]
        assert set(visible_tokens) == {"hello", "test!", " space", "\n"}

        # Disable filter
        widget.latin_only_button.click()
        qt_app.processEvents()
        assert len(widget.token_widgets) == 7
    finally:
        widget.deleteLater()


def test_token_picker_space_prefix_filter(ensure_google_icon_font, qt_app):
    """Test that space-prefix filter works correctly."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token(" world", -0.2),
        create_test_single_position_token("test", -0.3),
        create_test_single_position_token(" space", -0.4),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Initially all 4 tokens should be visible
        assert len(widget.token_widgets) == 4

        # Enable space-prefix filter
        widget.space_prefix_button.click()
        qt_app.processEvents()

        # Should show only tokens with space prefix: " world", " space"
        assert len(widget.token_widgets) == 2
        visible_tokens = [w.text().split(" [")[0].replace("␣", " ") for w in widget.token_widgets]
        assert set(visible_tokens) == {" world", " space"}

        # Disable filter
        widget.space_prefix_button.click()
        qt_app.processEvents()
        assert len(widget.token_widgets) == 4
    finally:
        widget.deleteLater()


def test_token_picker_no_space_prefix_filter(ensure_google_icon_font, qt_app):
    """Test that no-space-prefix filter works correctly."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token(" world", -0.2),
        create_test_single_position_token("test", -0.3),
        create_test_single_position_token(" space", -0.4),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Initially all 4 tokens should be visible
        assert len(widget.token_widgets) == 4

        # Enable no-space-prefix filter
        widget.no_space_prefix_button.click()
        qt_app.processEvents()

        # Should show only tokens without space prefix: "hello", "test"
        assert len(widget.token_widgets) == 2
        visible_tokens = [w.text().split(" [")[0] for w in widget.token_widgets]
        assert set(visible_tokens) == {"hello", "test"}

        # Disable filter
        widget.no_space_prefix_button.click()
        qt_app.processEvents()
        assert len(widget.token_widgets) == 4
    finally:
        widget.deleteLater()


def test_token_picker_combined_filters(ensure_google_icon_font, qt_app):
    """Test that multiple filters work together with AND logic."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token(" world", -0.2),
        create_test_single_position_token(" test", -0.3),
        create_test_single_position_token(" space", -0.4),
        create_test_single_position_token("世界", -0.5),  # Chinese
        create_test_single_position_token(" 你好", -0.6),  # Chinese with space
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Initially all 6 tokens should be visible
        assert len(widget.token_widgets) == 6

        # Enable Latin-only AND space-prefix filters
        widget.latin_only_button.click()
        widget.space_prefix_button.click()
        qt_app.processEvents()

        # Should show only Latin tokens with space prefix: " world", " test", " space"
        assert len(widget.token_widgets) == 3
        visible_tokens = [w.text().split(" [")[0].replace("␣", " ") for w in widget.token_widgets]
        assert set(visible_tokens) == {" world", " test", " space"}

        # Add text search filter "test"
        widget.search_input.setText("test")
        qt_app.processEvents()

        # Should show only " test" (Latin, space prefix, contains "test")
        assert len(widget.token_widgets) == 1
        assert widget.token_widgets[0].text().split(" [")[0].replace("␣", " ") == " test"

        # Clear all filters
        widget.search_input.setText("")
        widget.latin_only_button.click()
        widget.space_prefix_button.click()
        qt_app.processEvents()
        assert len(widget.token_widgets) == 6
    finally:
        widget.deleteLater()


def test_token_picker_filter_preserves_selection(ensure_google_icon_font, qt_app):
    """Test that filtering doesn't affect selected tokens that are still visible."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("hello", -0.1),
        create_test_single_position_token("world", -0.2),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=True)
    qt_app.processEvents()

    try:
        # Select first token
        first_checkbox = widget.token_widgets[0]
        first_checkbox.setChecked(True)
        qt_app.processEvents()

        # Verify selection
        assert len(widget.get_selected_tokens()) == 1
        assert widget.get_selected_tokens()[0].token_str == "hello"

        # Apply filter that keeps the selected token visible
        widget.search_input.setText("hel")
        qt_app.processEvents()

        # Selection should be preserved
        assert len(widget.get_selected_tokens()) == 1
        assert widget.get_selected_tokens()[0].token_str == "hello"

        # Clear filter
        widget.search_input.setText("")
        qt_app.processEvents()

        # Selection should still be preserved
        assert len(widget.get_selected_tokens()) == 1
    finally:
        widget.deleteLater()


def test_token_picker_is_latin_or_punctuation(ensure_google_icon_font, qt_app):
    """Test the _is_latin_or_punctuation helper method."""
    # pylint: disable=protected-access
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    tokens = SinglePositionTopLogprobs([create_test_single_position_token("test", -0.1)])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Test various strings
        assert widget._is_latin_or_punctuation("hello") is True
        assert widget._is_latin_or_punctuation("Hello World!") is True
        assert widget._is_latin_or_punctuation("test-123") is True
        assert widget._is_latin_or_punctuation("café") is True  # Latin with accents
        assert widget._is_latin_or_punctuation(" \n\t") is True  # Whitespace
        assert widget._is_latin_or_punctuation(".,!?;:") is True  # Punctuation

        assert widget._is_latin_or_punctuation("世界") is False  # Chinese
        assert widget._is_latin_or_punctuation("مرحبا") is False  # Arabic
        assert widget._is_latin_or_punctuation("Привет") is False  # Cyrillic
        assert widget._is_latin_or_punctuation("hello世界") is False  # Mixed
    finally:
        widget.deleteLater()
