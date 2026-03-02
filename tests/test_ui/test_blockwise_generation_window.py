"""
Tests for the Blockwise Generation UI components.

Covers WindowBlockwiseGeneration layout, BlockCandidateWidget, candidate grid,
acceptance flow, editing, saving, and WidgetSample integration.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from py_fade.controllers.blockwise_generation_controller import BlockCandidate, BlockwiseGenerationController
from py_fade.gui.window_blockwise_generation import BlockCandidateWidget, WindowBlockwiseGeneration
from py_fade.providers.mock_provider import MockLLMProvider
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mapped_model() -> MappedModel:
    """
    Create a real MappedModel with MockLLMProvider for deterministic tests.
    """
    provider = MockLLMProvider()
    return MappedModel("mock-echo-model", provider)


@pytest.fixture
def blockwise_window(app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None,
                     mock_mapped_model: MappedModel) -> WindowBlockwiseGeneration:
    """
    Create a WindowBlockwiseGeneration for testing.
    """
    _ = ensure_google_icon_font
    window = WindowBlockwiseGeneration(
        parent=None,
        app=app_with_dataset,
        prompt="Write a short story about a robot.",
        sample_widget=None,
        mapped_model=mock_mapped_model,
    )
    window.show()
    qt_app.processEvents()
    return window


# ---------------------------------------------------------------------------
# Test WindowBlockwiseGeneration layout
# ---------------------------------------------------------------------------


class TestWindowBlockwiseGenerationLayout:
    """
    Test the three-pane layout of the blockwise generation window.
    """

    def test_window_has_three_panes(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Window should have the main splitter, left pane, right splitter with two children.
        """
        assert blockwise_window.main_splitter is not None
        assert blockwise_window.left_pane is not None
        assert blockwise_window.right_splitter is not None
        assert blockwise_window.settings_pane is not None
        assert blockwise_window.candidates_pane is not None

    def test_prompt_display_shows_prompt(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        The prompt display shows the original prompt text.
        """
        assert blockwise_window.prompt_display.toPlainText() == "Write a short story about a robot."

    def test_completion_text_starts_empty(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        The completion text area starts empty.
        """
        assert blockwise_window.completion_text.toPlainText() == ""

    def test_completion_text_is_readonly_by_default(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        The completion text area is read-only by default.
        """
        assert blockwise_window.completion_text.isReadOnly()

    def test_status_label_shows_ready(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Status label shows 'Ready' initially.
        """
        assert blockwise_window.status_label.text() == "Ready"

    def test_width_spin_default_value(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Width spin box has default value of 4.
        """
        assert blockwise_window.width_spin.value() == 4

    def test_temperature_spin_default(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Temperature spin box has default value matching app config.
        """
        expected = int(blockwise_window.app.config.default_temperature * 100)
        assert blockwise_window.temperature_spin.value() == expected

    def test_top_k_spin_default(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Top-K spin box has default value matching app config.
        """
        assert blockwise_window.top_k_spin.value() == blockwise_window.app.config.default_top_k


# ---------------------------------------------------------------------------
# Test BlockCandidateWidget
# ---------------------------------------------------------------------------


class TestBlockCandidateWidget:
    """
    Test the BlockCandidateWidget display and buttons.
    """

    def test_widget_displays_text(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Widget displays the candidate block text.
        """
        _ = ensure_google_icon_font
        candidate = BlockCandidate(text="Test paragraph.\n", word_count=2, token_count=5)
        widget = BlockCandidateWidget(candidate)
        widget.show()
        qt_app.processEvents()

        assert widget.text_display.toPlainText() == "Test paragraph.\n"

    def test_widget_shows_word_count(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Widget shows word count in stats label.
        """
        _ = ensure_google_icon_font
        candidate = BlockCandidate(text="Three word text.\n", word_count=3, token_count=4)
        widget = BlockCandidateWidget(candidate)
        widget.show()
        qt_app.processEvents()

        assert "Words: 3" in widget.word_count_label.text()

    def test_widget_shows_token_count(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Widget shows token count in stats label.
        """
        _ = ensure_google_icon_font
        candidate = BlockCandidate(text="Text.\n", word_count=1, token_count=7)
        widget = BlockCandidateWidget(candidate)
        widget.show()
        qt_app.processEvents()

        assert "Tokens: 7" in widget.token_count_label.text()

    def test_widget_has_action_buttons(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Widget has all required action buttons.
        """
        _ = ensure_google_icon_font
        candidate = BlockCandidate(text="Text.\n", word_count=1, token_count=1)
        widget = BlockCandidateWidget(candidate)
        widget.show()
        qt_app.processEvents()

        assert widget.accept_button is not None
        assert widget.edit_button is not None
        assert widget.rewrite_button is not None
        assert widget.shorter_button is not None
        assert widget.longer_button is not None


# ---------------------------------------------------------------------------
# Test candidate grid management
# ---------------------------------------------------------------------------


class TestCandidateGrid:
    """
    Test candidate grid layout and widget management.
    """

    def test_add_candidate_widget(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Adding a candidate widget increases the widget count.
        """
        candidate = BlockCandidate(text="Block one.\n", word_count=2, token_count=3)
        blockwise_window._add_candidate_widget(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert len(blockwise_window.candidate_widgets) == 1

    def test_add_multiple_candidate_widgets(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Adding multiple candidate widgets works correctly.
        """
        for i in range(3):
            candidate = BlockCandidate(text=f"Block {i}.\n", word_count=2, token_count=3)
            blockwise_window._add_candidate_widget(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert len(blockwise_window.candidate_widgets) == 3

    def test_clear_candidate_widgets(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Clearing candidate widgets removes all widgets.
        """
        for i in range(3):
            candidate = BlockCandidate(text=f"Block {i}.\n", word_count=2, token_count=3)
            blockwise_window._add_candidate_widget(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        blockwise_window._clear_candidate_widgets()  # pylint: disable=protected-access
        assert len(blockwise_window.candidate_widgets) == 0


# ---------------------------------------------------------------------------
# Test block acceptance flow
# ---------------------------------------------------------------------------


class TestBlockAcceptanceFlow:
    """
    Test the block acceptance flow in the UI.
    """

    def test_accept_updates_completion_text(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Accepting a candidate updates the completion text display.
        """
        candidate = BlockCandidate(text="Accepted text.\n", word_count=2, token_count=4)
        blockwise_window.controller.candidates.append(candidate)
        blockwise_window._add_candidate_widget(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        blockwise_window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert blockwise_window.completion_text.toPlainText() == "Accepted text.\n"

    def test_accept_clears_candidate_widgets(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Accepting a candidate clears all candidate widgets.
        """
        candidate = BlockCandidate(text="Block.\n", word_count=1, token_count=2)
        blockwise_window.controller.candidates.append(candidate)
        blockwise_window._add_candidate_widget(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        blockwise_window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert len(blockwise_window.candidate_widgets) == 0

    def test_accept_multiple_blocks(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Accepting multiple blocks builds up the completion text.
        """
        c1 = BlockCandidate(text="First.\n", word_count=1, token_count=1)
        blockwise_window.controller.candidates.append(c1)
        blockwise_window._on_accept_candidate(c1)  # pylint: disable=protected-access
        qt_app.processEvents()

        c2 = BlockCandidate(text="Second.\n", word_count=1, token_count=1)
        blockwise_window.controller.candidates.append(c2)
        blockwise_window._on_accept_candidate(c2)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert blockwise_window.completion_text.toPlainText() == "First.\nSecond.\n"

    def test_accept_marks_unsaved(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Accepting a candidate marks the completion as unsaved.
        """
        blockwise_window.is_saved = True
        candidate = BlockCandidate(text="Block.\n", word_count=1, token_count=2)
        blockwise_window.controller.candidates.append(candidate)
        blockwise_window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert blockwise_window.is_saved is False


# ---------------------------------------------------------------------------
# Test edit toggle
# ---------------------------------------------------------------------------


class TestEditToggle:
    """
    Test the edit toggle button for the completion text.
    """

    def test_edit_toggle_enables_editing(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Toggling the edit button enables editing.
        """
        blockwise_window._on_edit_toggled(True)  # pylint: disable=protected-access
        assert blockwise_window.completion_text.isReadOnly() is False

    def test_edit_toggle_disables_editing(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Toggling the edit button off disables editing.
        """
        blockwise_window._on_edit_toggled(True)  # pylint: disable=protected-access
        blockwise_window._on_edit_toggled(False)  # pylint: disable=protected-access
        assert blockwise_window.completion_text.isReadOnly() is True


# ---------------------------------------------------------------------------
# Test save completion
# ---------------------------------------------------------------------------


class TestSaveCompletion:
    """
    Test saving the completion from the blockwise generation window.
    """

    def test_save_with_sample_widget(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None,
                                     mock_mapped_model: MappedModel, temp_dataset: "DatasetDatabase") -> None:
        """
        Saving completion with sample widget calls add_completion.
        """
        _ = ensure_google_icon_font
        mock_sample_widget = MagicMock()
        mock_sample_widget.add_completion = MagicMock()

        window = WindowBlockwiseGeneration(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=mock_sample_widget,
            mapped_model=mock_mapped_model,
        )
        window.show()
        qt_app.processEvents()

        # Accept a block
        candidate = BlockCandidate(text="Saved block.\n", word_count=2, token_count=3)
        window.controller.candidates.append(candidate)
        window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        # Save
        window.save_completion()
        qt_app.processEvents()

        mock_sample_widget.add_completion.assert_called_once()
        assert window.is_saved is True

    def test_save_empty_completion_warns(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Saving an empty completion shows a warning.
        """
        from PyQt6.QtWidgets import QMessageBox  # pylint: disable=import-outside-toplevel

        warned = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *args, **kwargs: warned.append(True)))

        blockwise_window.save_completion()
        qt_app.processEvents()

        assert len(warned) == 1

    def test_save_without_sample_widget_warns(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None,
                                              mock_mapped_model: MappedModel, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Saving without a sample widget shows a warning.
        """
        _ = ensure_google_icon_font
        from PyQt6.QtWidgets import QMessageBox  # pylint: disable=import-outside-toplevel

        warned = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *args, **kwargs: warned.append(True)))

        window = WindowBlockwiseGeneration(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=None,
            mapped_model=mock_mapped_model,
        )
        window.show()
        qt_app.processEvents()

        # Accept a block first
        candidate = BlockCandidate(text="Block.\n", word_count=1, token_count=1)
        window.controller.candidates.append(candidate)
        window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        window.save_completion()
        qt_app.processEvents()

        assert len(warned) == 1


# ---------------------------------------------------------------------------
# Test generation with mock provider
# ---------------------------------------------------------------------------


class TestGenerationWithMockProvider:
    """
    Test blockwise generation using the mock provider.
    """

    def test_generate_blocks_creates_candidates(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Clicking generate produces candidate widgets.
        """
        blockwise_window.width_spin.setValue(2)
        blockwise_window.generate_blocks()
        qt_app.processEvents()

        assert len(blockwise_window.candidate_widgets) > 0

    def test_generate_updates_status(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Generation updates the status label.
        """
        blockwise_window.width_spin.setValue(1)
        blockwise_window.generate_blocks()
        qt_app.processEvents()

        status = blockwise_window.status_label.text()
        assert "Generated" in status or "candidates" in status.lower()


# ---------------------------------------------------------------------------
# Test gutter stats
# ---------------------------------------------------------------------------


class TestGutterStats:
    """
    Test the gutter stats display.
    """

    def test_initial_gutter_stats(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Initial gutter stats show zero blocks and words.
        """
        assert "Blocks: 0" in blockwise_window.gutter_label.text()

    def test_gutter_stats_after_accept(self, blockwise_window: WindowBlockwiseGeneration, qt_app: QApplication) -> None:
        """
        Gutter stats update after accepting a block.
        """
        candidate = BlockCandidate(text="Hello world text.\n", word_count=3, token_count=4)
        blockwise_window.controller.candidates.append(candidate)
        blockwise_window._on_accept_candidate(candidate)  # pylint: disable=protected-access
        qt_app.processEvents()

        assert "Blocks: 1" in blockwise_window.gutter_label.text()


# ---------------------------------------------------------------------------
# Test WidgetSample button
# ---------------------------------------------------------------------------


class TestWidgetSampleBlockwiseButton:
    """
    Test the blockwise generation button on the WidgetSample.
    """

    def test_blockwise_button_exists(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        WidgetSample has a blockwise generation button.
        """
        _ = ensure_google_icon_font
        from py_fade.gui.widget_sample import WidgetSample  # pylint: disable=import-outside-toplevel

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert hasattr(widget, 'blockwise_button')
        assert widget.blockwise_button is not None

    def test_blockwise_button_tooltip(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Blockwise button has the correct tooltip.
        """
        _ = ensure_google_icon_font
        from py_fade.gui.widget_sample import WidgetSample  # pylint: disable=import-outside-toplevel

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert widget.blockwise_button.toolTip() == "Blockwise Generation"

    def test_open_blockwise_without_prompt_warns(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Opening blockwise generation without a prompt shows a warning.
        """
        _ = ensure_google_icon_font
        from PyQt6.QtWidgets import QMessageBox  # pylint: disable=import-outside-toplevel
        from py_fade.gui.widget_sample import WidgetSample  # pylint: disable=import-outside-toplevel

        warned = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *args, **kwargs: warned.append(True)))

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        widget.open_blockwise_generation()
        qt_app.processEvents()

        assert len(warned) == 1

    def test_open_blockwise_without_model_warns(self, app_with_dataset: "pyFadeApp", qt_app: QApplication, ensure_google_icon_font: None,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Opening blockwise generation without a model shows a warning.
        """
        _ = ensure_google_icon_font
        from PyQt6.QtWidgets import QMessageBox  # pylint: disable=import-outside-toplevel
        from py_fade.gui.widget_sample import WidgetSample  # pylint: disable=import-outside-toplevel

        warned = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *args, **kwargs: warned.append(True)))

        widget = WidgetSample(None, app_with_dataset, None)
        widget.prompt_area.setPlainText("Test prompt")
        widget.active_model = None
        widget.show()
        qt_app.processEvents()

        widget.open_blockwise_generation()
        qt_app.processEvents()

        assert len(warned) == 1


# ---------------------------------------------------------------------------
# Test controller settings sync
# ---------------------------------------------------------------------------


class TestControllerSettingsSync:
    """
    Test that UI settings are synced to the controller.
    """

    def test_sync_global_instructions(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Global instructions field value is synced to controller.
        """
        blockwise_window.global_instructions_field.setPlainText("Be creative")
        blockwise_window._sync_controller_settings()  # pylint: disable=protected-access
        assert blockwise_window.controller.global_instructions == "Be creative"

    def test_sync_block_instructions(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Block instructions field value is synced to controller.
        """
        blockwise_window.block_instructions_field.setPlainText("[formal style]")
        blockwise_window._sync_controller_settings()  # pylint: disable=protected-access
        assert blockwise_window.controller.block_instructions == "[formal style]"

    def test_sync_manual_prefix(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Manual prefix field value is synced to controller.
        """
        blockwise_window.manual_prefix_field.setPlainText("The robot")
        blockwise_window._sync_controller_settings()  # pylint: disable=protected-access
        assert blockwise_window.controller.manual_prefix == "The robot"

    def test_sync_temperature(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Temperature spin value is synced to controller as float.
        """
        blockwise_window.temperature_spin.setValue(90)
        blockwise_window._sync_controller_settings()  # pylint: disable=protected-access
        assert blockwise_window.controller.temperature == pytest.approx(0.9)

    def test_sync_top_k(self, blockwise_window: WindowBlockwiseGeneration) -> None:
        """
        Top-K spin value is synced to controller.
        """
        blockwise_window.top_k_spin.setValue(50)
        blockwise_window._sync_controller_settings()  # pylint: disable=protected-access
        assert blockwise_window.controller.top_k == 50
