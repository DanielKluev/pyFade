"""
Test Token Picker test module.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QPushButton

from py_fade.gui.components.widget_token_picker import WidgetTokenPicker
from py_fade.data_formats.base_data_classes import SinglePositionTopLogprobs
from tests.helpers.data_helpers import create_test_single_position_token


def test_token_picker_normalises_llm_logprob_objects(qt_app):
    """Test that token picker properly normalizes SinglePositionToken objects."""
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("B", -1.2),
        create_test_single_position_token("A", -0.4),
        create_test_single_position_token("C", -3.1),
    ])

    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    qt_app.processEvents()

    try:
        # Sorted descending by logprob (less negative first).
        assert [token for token, _ in widget.tokens] == ["A", "B", "C"]
    finally:
        widget.deleteLater()


def test_token_picker_single_select_emits_selected_tokens(qt_app):
    """Test that token picker in single-select mode emits selected tokens immediately."""
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("first", -0.1),
        create_test_single_position_token("second", -0.3),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=False)
    captured: list[list[tuple[str, float]]] = []
    widget.tokens_selected.connect(lambda payload: captured.append(list(payload)))

    try:
        first_button = widget.token_widgets[0]
        assert isinstance(first_button, QPushButton)
        first_button.click()
        qt_app.processEvents()

        assert captured
        assert set(captured[-1]) == {("first", -0.1)}

        # Selecting the second token should replace the selection.
        second_button = widget.token_widgets[1]
        assert isinstance(second_button, QPushButton)
        second_button.click()
        qt_app.processEvents()

        assert set(captured[-1]) == {("second", -0.3)}
        assert not first_button.isChecked()
    finally:
        widget.deleteLater()


def test_token_picker_multi_select_requires_accept(qt_app):
    """Test that token picker in multi-select mode requires explicit accept action."""
    tokens = SinglePositionTopLogprobs([
        create_test_single_position_token("alpha", -0.5),
        create_test_single_position_token("beta", -0.2),
        create_test_single_position_token("gamma", -1.1),
    ])
    widget = WidgetTokenPicker(None, tokens, multi_select=True)
    captured: list[list[tuple[str, float]]] = []
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
        assert set(captured[-1]) == {("alpha", -0.5), ("beta", -0.2)}

        widget.clear_selection()
        qt_app.processEvents()

        assert not widget.get_selected_tokens()
        assert not first_checkbox.isChecked()
        assert not second_checkbox.isChecked()
    finally:
        widget.deleteLater()
