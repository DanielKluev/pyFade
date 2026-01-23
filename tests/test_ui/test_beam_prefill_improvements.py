"""
Unit tests for beam search window prefill improvements.

Tests focus on:
1. Prefill history management (max 50 items, no duplicates, most recent first)
2. Increased prefill field height (minimum 90px instead of 60px)
3. "Use as Prefill" button functionality in beam completion frames
4. History combobox integration and selection
"""

import logging

import pytest
from PyQt6.QtCore import Qt

from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from py_fade.gui.components.widget_completion import CompletionFrame
from tests.helpers.data_helpers import create_llm_response_with_logprobs
from tests.helpers.ui_helpers import create_mock_mapped_model

logger = logging.getLogger(__name__)


class TestBeamPrefillHistory:
    """
    Test prefill history management in beam search window.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_prefill_history_initialized_empty(self, app_with_dataset):
        """
        Test that prefill history is initialized as empty list.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify history is empty
        assert widget.prefill_history == []
        assert widget.prefill_history_combo.count() == 1
        assert widget.prefill_history_combo.itemText(0) == "(No history)"

    def test_add_prefill_to_history(self, app_with_dataset):
        """
        Test that adding prefill text to history works correctly.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add first item
        widget._add_to_prefill_history("First prefill")  # pylint: disable=protected-access

        assert len(widget.prefill_history) == 1
        assert widget.prefill_history[0] == "First prefill"
        assert widget.prefill_history_combo.count() == 1
        assert "First prefill" in widget.prefill_history_combo.itemText(0)

    def test_add_multiple_prefills_to_history(self, app_with_dataset):
        """
        Test that multiple prefills are added correctly with most recent first.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add multiple items
        widget._add_to_prefill_history("First")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Second")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Third")  # pylint: disable=protected-access

        # Verify order (most recent first)
        assert len(widget.prefill_history) == 3
        assert widget.prefill_history[0] == "Third"
        assert widget.prefill_history[1] == "Second"
        assert widget.prefill_history[2] == "First"

    def test_no_duplicate_prefills_in_history(self, app_with_dataset):
        """
        Test that duplicate prefills are not added to history.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add same item multiple times
        widget._add_to_prefill_history("Same prefill")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Different")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Same prefill")  # pylint: disable=protected-access

        # Verify no duplicates and "Same prefill" is moved to top
        assert len(widget.prefill_history) == 2
        assert widget.prefill_history[0] == "Same prefill"
        assert widget.prefill_history[1] == "Different"

    def test_history_max_50_items(self, app_with_dataset):
        """
        Test that history maintains maximum of 50 items.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add 60 items
        for i in range(60):
            widget._add_to_prefill_history(f"Prefill {i}")  # pylint: disable=protected-access

        # Verify only 50 items kept, most recent first
        assert len(widget.prefill_history) == 50
        assert widget.prefill_history[0] == "Prefill 59"
        assert widget.prefill_history[49] == "Prefill 10"
        # "Prefill 0" through "Prefill 9" should have been removed

    def test_empty_or_whitespace_prefill_not_added(self, app_with_dataset):
        """
        Test that empty or whitespace-only prefills are not added to history.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Try to add empty and whitespace items
        widget._add_to_prefill_history("")  # pylint: disable=protected-access
        widget._add_to_prefill_history("   ")  # pylint: disable=protected-access
        widget._add_to_prefill_history("\n\t")  # pylint: disable=protected-access

        # Verify history is still empty
        assert len(widget.prefill_history) == 0
        assert widget.prefill_history_combo.count() == 1
        assert widget.prefill_history_combo.itemText(0) == "(No history)"

    def test_prefill_added_to_history_on_generation(self, app_with_dataset, monkeypatch):
        """
        Test that prefill is automatically added to history when generation starts.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Set prefill text
        widget.prefill_edit.setPlainText("Test prefill for generation")

        # Mock the worker thread to prevent actual generation
        monkeypatch.setattr(widget, "worker_thread", None)

        # Mock app methods to prevent errors
        def mock_get_mapped_model(_text):
            return mapped_model

        monkeypatch.setattr(widget.app.providers_manager, "get_mapped_model", mock_get_mapped_model)

        # Mock controller creation
        def mock_get_or_create_controller():
            from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel
            return MagicMock()

        monkeypatch.setattr(widget, "_get_or_create_beam_controller", mock_get_or_create_controller)

        # Trigger generation (which should add prefill to history)
        widget.generate_beams()

        # Verify prefill was added to history
        assert len(widget.prefill_history) == 1
        assert widget.prefill_history[0] == "Test prefill for generation"


class TestBeamPrefillHistoryCombobox:
    """
    Test prefill history combobox functionality.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_history_combo_shows_no_history_when_empty(self, app_with_dataset):
        """
        Test that combobox shows "(No history)" when history is empty.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        assert widget.prefill_history_combo.count() == 1
        assert widget.prefill_history_combo.itemText(0) == "(No history)"

    def test_history_combo_populated_with_items(self, app_with_dataset):
        """
        Test that combobox is populated with history items.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add items
        widget._add_to_prefill_history("First item")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Second item")  # pylint: disable=protected-access

        # Verify combobox has items
        assert widget.prefill_history_combo.count() == 2
        assert "Second item" in widget.prefill_history_combo.itemText(0)
        assert "First item" in widget.prefill_history_combo.itemText(1)

    def test_selecting_history_item_sets_prefill(self, app_with_dataset, qtbot):
        """
        Test that selecting an item from history sets the prefill text.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Add items
        widget._add_to_prefill_history("First prefill")  # pylint: disable=protected-access
        widget._add_to_prefill_history("Second prefill")  # pylint: disable=protected-access

        # Select first item (index 0, which is "Second prefill")
        widget.prefill_history_combo.setCurrentIndex(0)
        qtbot.wait(50)  # Wait for signal processing

        # Verify prefill text was set
        assert widget.prefill_edit.toPlainText() == "Second prefill"

    def test_selecting_history_item_saves_current_prefill(self, app_with_dataset, qtbot):
        """
        Test that selecting an item from history saves the current prefill before replacing.

        This is the bug fix test: when user edits prefill and then selects from history,
        the edited prefill should be saved to history before being replaced.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Add some items to history
        widget._add_to_prefill_history("History item 1")  # pylint: disable=protected-access
        widget._add_to_prefill_history("History item 2")  # pylint: disable=protected-access

        # Verify initial state: 2 items in history
        assert len(widget.prefill_history) == 2
        assert widget.prefill_history[0] == "History item 2"
        assert widget.prefill_history[1] == "History item 1"

        # User manually edits the prefill field
        widget.prefill_edit.setPlainText("Current edited prefill")

        # User selects an item from history (index 1 is "History item 1")
        widget.prefill_history_combo.setCurrentIndex(1)
        qtbot.wait(50)  # Wait for signal processing

        # Verify prefill was replaced with selected item
        assert widget.prefill_edit.toPlainText() == "History item 1"

        # BUG FIX: Verify the edited prefill was saved to history before being replaced
        assert len(widget.prefill_history) == 3
        assert "Current edited prefill" in widget.prefill_history
        # Most recent should be the saved prefill
        assert widget.prefill_history[0] == "Current edited prefill"

    def test_selecting_history_item_with_empty_current_prefill(self, app_with_dataset, qtbot):
        """
        Test that selecting from history with empty current prefill doesn't add empty to history.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Add items to history
        widget._add_to_prefill_history("History item 1")  # pylint: disable=protected-access
        widget._add_to_prefill_history("History item 2")  # pylint: disable=protected-access

        # Leave prefill empty (default state)
        assert widget.prefill_edit.toPlainText() == ""

        # Select from history
        widget.prefill_history_combo.setCurrentIndex(0)
        qtbot.wait(50)

        # Verify prefill was set
        assert widget.prefill_edit.toPlainText() == "History item 2"

        # Verify empty prefill was NOT added to history
        assert len(widget.prefill_history) == 2
        assert "" not in widget.prefill_history

    def test_long_prefill_truncated_in_combo(self, app_with_dataset):
        """
        Test that long prefill items are truncated in combobox display.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add a very long prefill (over 100 characters)
        long_text = "A" * 150
        widget._add_to_prefill_history(long_text)  # pylint: disable=protected-access

        # Verify display text is truncated
        display_text = widget.prefill_history_combo.itemText(0)
        assert len(display_text) <= 103  # 100 chars + "..."
        assert display_text.endswith("...")

    def test_multiline_prefill_shown_as_single_line_in_combo(self, app_with_dataset):
        """
        Test that multiline prefills are shown as single line in combobox.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add multiline prefill
        multiline_text = "Line 1\nLine 2\nLine 3"
        widget._add_to_prefill_history(multiline_text)  # pylint: disable=protected-access

        # Verify display text has no newlines
        display_text = widget.prefill_history_combo.itemText(0)
        assert "\n" not in display_text
        assert "\r" not in display_text
        assert "Line 1 Line 2 Line 3" == display_text


class TestBeamPrefillFieldHeight:
    """
    Test that prefill field has increased height.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_prefill_field_minimum_height(self, app_with_dataset):
        """
        Test that prefill field has minimum height of 90px (increased from 60px).
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify minimum height is at least 90px
        assert widget.prefill_edit.minimumHeight() >= 90

    def test_prefill_field_maximum_height(self, app_with_dataset):
        """
        Test that prefill field has reasonable maximum height.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify maximum height is set (to prevent excessive growth)
        assert widget.prefill_edit.maximumHeight() <= 200


class TestUseAsPrefillButton:
    """
    Test "Use as Prefill" button functionality in beam completion frames.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_beam_frame_has_use_as_prefill_button(self, app_with_dataset):
        """
        Test that beam mode completion frames have "Use as Prefill" button.
        """
        beam = create_llm_response_with_logprobs("test-model", "Beam completion text", -1.0)
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Verify button exists
        assert frame.use_as_prefill_button is not None
        assert frame.use_as_prefill_button.toolTip() == "Use this completion text as prefill"

    def test_sample_frame_no_use_as_prefill_button(self, app_with_dataset):
        """
        Test that sample mode completion frames do NOT have "Use as Prefill" button.
        """
        # Use LLMResponse but in sample mode (still shouldn't have the button)
        beam = create_llm_response_with_logprobs("test-model", "Sample completion", -1.0)
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="sample")

        # Verify button does not exist in sample mode
        assert frame.use_as_prefill_button is None

    def test_use_as_prefill_button_click_emits_signal(self, app_with_dataset, qtbot):
        """
        Test that clicking "Use as Prefill" button emits signal with completion text.
        """
        beam = create_llm_response_with_logprobs("test-model", "Beam text to use as prefill", -1.0)
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Connect to signal
        emitted_texts = []

        def on_signal(text):
            emitted_texts.append(text)

        frame.use_as_prefill_requested.connect(on_signal)

        # Click button
        qtbot.mouseClick(frame.use_as_prefill_button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Verify signal was emitted with correct text
        assert len(emitted_texts) == 1
        assert emitted_texts[0] == "Beam text to use as prefill"

    def test_use_as_prefill_replaces_current_prefill(self, app_with_dataset, qtbot):
        """
        Test that using beam as prefill replaces current prefill text.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Set initial prefill
        widget.prefill_edit.setPlainText("Initial prefill")

        # Add a beam
        beam = create_llm_response_with_logprobs("test-model", "New prefill from beam", -1.5)
        widget.add_beam_frame(beam)

        # Get the frame
        _beam, frame = widget.beam_frames[0]

        # Click "Use as Prefill" button
        qtbot.mouseClick(frame.use_as_prefill_button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Verify prefill was replaced
        assert widget.prefill_edit.toPlainText() == "New prefill from beam"

    def test_use_as_prefill_saves_old_prefill_to_history(self, app_with_dataset, qtbot):
        """
        Test that using beam as prefill saves the old prefill to history.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Set initial prefill
        widget.prefill_edit.setPlainText("Old prefill to save")

        # Add a beam
        beam = create_llm_response_with_logprobs("test-model", "New prefill", -1.5)
        widget.add_beam_frame(beam)

        # Get the frame
        _beam, frame = widget.beam_frames[0]

        # Click "Use as Prefill" button
        qtbot.mouseClick(frame.use_as_prefill_button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Verify old prefill was saved to history
        assert len(widget.prefill_history) == 1
        assert widget.prefill_history[0] == "Old prefill to save"

    def test_use_as_prefill_with_empty_current_prefill(self, app_with_dataset, qtbot):
        """
        Test that using beam as prefill works when current prefill is empty.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Leave prefill empty
        assert widget.prefill_edit.toPlainText() == ""

        # Add a beam
        beam = create_llm_response_with_logprobs("test-model", "Beam text", -1.0)
        widget.add_beam_frame(beam)

        # Get the frame
        _beam, frame = widget.beam_frames[0]

        # Click "Use as Prefill" button
        qtbot.mouseClick(frame.use_as_prefill_button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Verify prefill was set and history remains empty (empty prefill not saved)
        assert widget.prefill_edit.toPlainText() == "Beam text"
        assert len(widget.prefill_history) == 0


class TestBeamPrefillIntegration:
    """
    Integration tests for prefill history and "Use as Prefill" features.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_full_workflow_with_history_and_use_as_prefill(self, app_with_dataset, qtbot, monkeypatch):
        """
        Test complete workflow: generate with prefill, use beam as prefill, select from history.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Step 1: Set initial prefill and mock generation
        widget.prefill_edit.setPlainText("First prefill")

        # Mock to prevent actual generation
        monkeypatch.setattr(widget, "worker_thread", None)

        def mock_get_mapped_model(_text):
            return mapped_model

        monkeypatch.setattr(widget.app.providers_manager, "get_mapped_model", mock_get_mapped_model)

        def mock_get_or_create_controller():
            from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel
            return MagicMock()

        monkeypatch.setattr(widget, "_get_or_create_beam_controller", mock_get_or_create_controller)

        widget.generate_beams()

        # Verify first prefill in history
        assert len(widget.prefill_history) == 1
        assert widget.prefill_history[0] == "First prefill"

        # Step 2: Add a beam and use it as prefill
        beam = create_llm_response_with_logprobs("test-model", "Beam completion", -1.0)
        widget.add_beam_frame(beam)

        _beam, frame = widget.beam_frames[0]
        qtbot.mouseClick(frame.use_as_prefill_button, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Verify prefill was replaced and old one saved
        assert widget.prefill_edit.toPlainText() == "Beam completion"
        assert len(widget.prefill_history) == 1  # Still 1 because "First prefill" already in history

        # Step 3: Select from history
        widget.prefill_history_combo.setCurrentIndex(0)
        qtbot.wait(50)

        # Verify prefill restored from history
        assert widget.prefill_edit.toPlainText() == "First prefill"
