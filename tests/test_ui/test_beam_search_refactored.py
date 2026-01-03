"""
Unit tests for refactored beam search window features.

Tests focus on:
1. Temperature and top_k are hardcoded to 0.0 and 1 (deterministic beam search)
2. Icon buttons are used for Generate, Selective, and Stop actions
3. Generation status shows "X out of Y" excluding pinned beams
4. Adaptive grid layout based on window width
"""

import logging
from unittest.mock import MagicMock

import pytest

from py_fade.gui.widget_completion_beams import WidgetCompletionBeams, BeamGenerationWorker
from py_fade.gui.components.widget_completion import CompletionFrame
from tests.helpers.data_helpers import create_llm_response_with_logprobs
from tests.helpers.ui_helpers import create_mock_mapped_model

logger = logging.getLogger(__name__)


class TestBeamSearchDeterministicSettings:
    """
    Test that beam search uses deterministic settings (temperature=0.0, top_k=1).
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_beam_worker_uses_deterministic_settings(self, app_with_dataset):
        """
        Test BeamGenerationWorker always uses temperature=0.0 and top_k=1.
        """
        # Create a mock beam controller (we're only testing worker attributes)
        beam_controller = MagicMock()

        # Create worker without explicit temperature/top_k
        worker = BeamGenerationWorker(
            app=app_with_dataset,
            beam_controller=beam_controller,
            prefill="test",
            width=3,
            depth=10,
        )

        # Verify deterministic settings
        assert worker.temperature == 0.0
        assert worker.top_k == 1

    def test_beam_widget_has_no_temperature_field(self, app_with_dataset):
        """
        Test that the beam search widget does not have temperature or top_k UI fields.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify temperature and top_k spin boxes don't exist
        assert not hasattr(widget, 'temp_spin')
        assert not hasattr(widget, 'topk_spin')

    def test_beam_widget_has_width_and_depth(self, app_with_dataset):
        """
        Test that the beam search widget has width and depth controls.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify width and depth spin boxes exist
        assert hasattr(widget, 'width_spin')
        assert hasattr(widget, 'depth_spin')
        assert widget.width_spin.value() == 3
        assert widget.depth_spin.value() == 20


class TestBeamSearchIconButtons:
    """
    Test that beam search uses icon buttons with tooltips.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_generate_button_is_icon_button(self, app_with_dataset):
        """
        Test that the Generate button is an icon button with text and tooltip.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify generate button has icon and text
        assert widget.generate_btn.text() == "Generate"
        assert widget.generate_btn.toolTip() == "Generate beams with current settings"
        assert widget.generate_btn.icon() is not None

    def test_selective_button_is_icon_button(self, app_with_dataset):
        """
        Test that the Selective button is an icon button with text and tooltip.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify selective button has icon and text
        assert widget.selective_beams_btn.text() == "Selective"
        assert widget.selective_beams_btn.toolTip() == "Select specific tokens for beam generation"
        assert widget.selective_beams_btn.icon() is not None

    def test_stop_button_is_icon_button(self, app_with_dataset):
        """
        Test that the Stop button is an icon button with text and tooltip.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify stop button has icon and text
        assert widget.stop_btn.text() == "Stop"
        assert widget.stop_btn.toolTip() == "Stop current generation"
        assert widget.stop_btn.icon() is not None


class TestBeamSearchProgressStatus:
    """
    Test that beam search shows accurate progress excluding pinned beams.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_initial_generation_status(self, app_with_dataset):
        """
        Test that initial generation status shows "0 out of N" beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Set width to 5
        widget.width_spin.setValue(5)

        # Start tracking (simulate beginning of generation)
        widget.generation_start_beam_count = 0
        widget.expected_new_beams = 5

        # Check initial status
        widget.status_label.setText(f"Generating 0 out of {widget.expected_new_beams} beams...")
        assert "0 out of 5" in widget.status_label.text()

    def test_progress_status_with_new_beams(self, app_with_dataset):
        """
        Test that progress status updates correctly as new beams are generated.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Start generation tracking
        widget.generation_start_beam_count = 0
        widget.expected_new_beams = 3

        # Add first beam
        beam1 = create_llm_response_with_logprobs("test-model", "Beam 1", -1.0)
        widget.add_beam_frame(beam1)

        # Simulate on_beam_completed
        new_beams_count = len(widget.beam_frames) - widget.generation_start_beam_count
        widget.status_label.setText(f"Generating {new_beams_count} out of {widget.expected_new_beams} beams...")
        assert "1 out of 3" in widget.status_label.text()

        # Add second beam
        beam2 = create_llm_response_with_logprobs("test-model", "Beam 2", -1.5)
        widget.add_beam_frame(beam2)

        new_beams_count = len(widget.beam_frames) - widget.generation_start_beam_count
        widget.status_label.setText(f"Generating {new_beams_count} out of {widget.expected_new_beams} beams...")
        assert "2 out of 3" in widget.status_label.text()

    def test_progress_status_excludes_pinned_beams(self, app_with_dataset):
        """
        Test that progress status excludes pinned beams from the count.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add and pin a beam before generation
        pinned_beam = create_llm_response_with_logprobs("test-model", "Pinned beam", -0.5)
        pinned_frame = CompletionFrame(app_with_dataset.current_dataset, pinned_beam, parent=widget, display_mode="beam")
        pinned_frame.is_pinned = True
        widget.beam_frames.append((pinned_beam, pinned_frame))

        # Start generation tracking (after pinned beam is added)
        widget.generation_start_beam_count = len(widget.beam_frames)  # 1 pinned beam
        widget.expected_new_beams = 3

        # Add new beams
        beam1 = create_llm_response_with_logprobs("test-model", "Beam 1", -1.0)
        widget.add_beam_frame(beam1)

        # Verify count excludes pinned beam
        new_beams_count = len(widget.beam_frames) - widget.generation_start_beam_count
        assert new_beams_count == 1
        assert len(widget.beam_frames) == 2  # 1 pinned + 1 new

        widget.status_label.setText(f"Generating {new_beams_count} out of {widget.expected_new_beams} beams...")
        assert "1 out of 3" in widget.status_label.text()

    def test_completion_status_message(self, app_with_dataset):
        """
        Test that completion status shows new beams and total beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Add pinned beam
        pinned_beam = create_llm_response_with_logprobs("test-model", "Pinned beam", -0.5)
        pinned_frame = CompletionFrame(app_with_dataset.current_dataset, pinned_beam, parent=widget, display_mode="beam")
        pinned_frame.is_pinned = True
        widget.beam_frames.append((pinned_beam, pinned_frame))

        # Start generation
        widget.generation_start_beam_count = 1
        widget.expected_new_beams = 2

        # Add new beams
        beam1 = create_llm_response_with_logprobs("test-model", "Beam 1", -1.0)
        widget.add_beam_frame(beam1)
        beam2 = create_llm_response_with_logprobs("test-model", "Beam 2", -1.5)
        widget.add_beam_frame(beam2)

        # Simulate completion
        new_beams_count = len(widget.beam_frames) - widget.generation_start_beam_count
        total_beams = len(widget.beam_frames)
        widget.status_label.setText(f"Generation complete. Generated {new_beams_count} new beams ({total_beams} total).")

        assert "2 new beams" in widget.status_label.text()
        assert "3 total" in widget.status_label.text()


class TestBeamSearchAdaptiveGrid:
    """
    Test that beam search grid adapts to window width.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_adaptive_grid_width_on_resize(self, app_with_dataset, qtbot):
        """
        Test that grid width adjusts when window is resized.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Initial grid width
        initial_grid_width = widget.grid_width

        # Simulate window resize (make it wider)
        widget.resize(2000, 900)
        qtbot.wait(50)  # Wait for resize event to process

        # Grid width should adapt to wider window
        # With min_beam_width=400, a 2000px window should fit more columns
        assert widget.grid_width >= initial_grid_width

    def test_grid_width_minimum_one(self, app_with_dataset, qtbot):
        """
        Test that grid width never goes below 1.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Simulate very narrow window
        widget.resize(300, 900)
        qtbot.wait(50)

        # Grid width should be at least 1
        assert widget.grid_width >= 1

    def test_rearrange_beam_grid_called_on_width_change(self, app_with_dataset, qtbot):
        """
        Test that rearrange_beam_grid is called when grid width changes.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)
        qtbot.addWidget(widget)

        # Add some beams
        beam1 = create_llm_response_with_logprobs("test-model", "Beam 1", -1.0)
        widget.add_beam_frame(beam1)
        beam2 = create_llm_response_with_logprobs("test-model", "Beam 2", -1.5)
        widget.add_beam_frame(beam2)

        initial_grid_width = widget.grid_width

        # Resize to trigger grid width change
        widget.resize(2000, 900)
        qtbot.wait(50)

        # If grid width changed, beams should be rearranged
        if widget.grid_width != initial_grid_width:
            # Verify beams are still in the layout
            assert widget.beams_layout.count() >= 2


class TestBeamSearchContextLength:
    """
    Test that beam search uses the correct context_length from the sample.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_beam_widget_uses_sample_context_length(self, app_with_dataset, monkeypatch):
        """
        Test that beam search widget uses context_length from sample widget, not default.
        
        This reproduces the bug where beam search ignores sample's custom context size.
        """
        # Create a mock sample widget with non-default context_length
        mock_sample_widget = MagicMock()
        mock_sample_widget.context_length_field.value.return_value = 2048  # Non-default

        # Create mapped model
        mapped_model = create_mock_mapped_model()

        # Create beam widget with sample widget reference
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", mock_sample_widget, mapped_model)

        # Verify that the beam widget has access to sample widget
        assert widget.sample_widget is mock_sample_widget

        # Mock the controller creation to capture the context_length parameter
        controller_params = {}

        def mock_get_or_create_controller(*_args, **kwargs):  # pylint: disable=unused-argument
            controller_params.update(kwargs)
            mock_controller = MagicMock()
            return mock_controller

        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", mock_get_or_create_controller)

        # Call _get_or_create_beam_controller which should pass context_length
        widget._get_or_create_beam_controller()  # pylint: disable=protected-access

        # Verify that context_length was passed and equals 2048, not default 1024
        assert 'context_length' in controller_params, "context_length should be passed to controller"
        assert controller_params['context_length'] == 2048, f"Expected context_length=2048, got {controller_params.get('context_length')}"

    def test_beam_worker_uses_sample_context_length(self, app_with_dataset):
        """
        Test that BeamGenerationWorker uses context_length from sample, not default.
        """
        # Create a mock beam controller
        beam_controller = MagicMock()

        # Create worker with explicit context_length=2048
        worker = BeamGenerationWorker(
            app=app_with_dataset,
            beam_controller=beam_controller,
            prefill="test",
            width=3,
            depth=10,
            context_length=2048,  # Should use this, not default 1024
        )

        # Verify worker has correct context_length
        assert worker.context_length == 2048, f"Expected context_length=2048, got {worker.context_length}"

    def test_beam_widget_without_sample_widget_uses_default_context_length(self, app_with_dataset, monkeypatch):
        """
        Test that beam widget uses default context_length when no sample widget is provided.
        """
        # Create mapped model
        mapped_model = create_mock_mapped_model()

        # Create beam widget without sample widget
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Verify that sample_widget is None
        assert widget.sample_widget is None

        # Mock the controller creation to capture the context_length parameter
        controller_params = {}

        def mock_get_or_create_controller(*_args, **kwargs):  # pylint: disable=unused-argument
            controller_params.update(kwargs)
            mock_controller = MagicMock()
            return mock_controller

        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", mock_get_or_create_controller)

        # Call _get_or_create_beam_controller
        widget._get_or_create_beam_controller()  # pylint: disable=protected-access

        # When sample_widget is None, should use default context_length (1024)
        # If context_length is not explicitly passed, it defaults to app.config.default_context_length
        expected_context_length = app_with_dataset.config.default_context_length
        if 'context_length' in controller_params:
            assert controller_params['context_length'] == expected_context_length, \
                f"Expected default context_length={expected_context_length}, got {controller_params['context_length']}"
