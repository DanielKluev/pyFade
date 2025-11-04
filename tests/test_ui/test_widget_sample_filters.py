"""
Test extended completions filters in WidgetSample.

Tests for the completions filter UI integration, including filter button interactions,
configuration persistence, and proper filtering behavior.
"""
from pathlib import Path

from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.components.widget_toggle_button import QPushButtonToggle
from py_fade.gui.gui_helpers import get_dataset_preferences, update_dataset_preferences
from py_fade.dataset.facet import Facet
from py_fade.dataset.completion_rating import PromptCompletionRating
from tests.helpers.data_helpers import create_test_sample, create_test_completion_with_params


class TestCompletionsFilterUI:
    """Test completions filter UI components."""

    def test_filter_buttons_exist(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that all filter buttons are created.
        """
        _ = ensure_google_icon_font
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Verify all filter buttons exist
        assert widget.filter_archived_button is not None
        assert widget.filter_other_models_button is not None
        assert widget.filter_other_families_button is not None
        assert widget.filter_rated_button is not None
        assert widget.filter_low_rated_button is not None
        assert widget.filter_unrated_button is not None
        assert widget.filter_full_button is not None
        assert widget.filter_truncated_button is not None

    def test_filter_buttons_are_toggle_buttons(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that filter buttons are QPushButtonToggle instances.
        """
        _ = ensure_google_icon_font
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Verify buttons are correct type
        assert isinstance(widget.filter_archived_button, QPushButtonToggle)
        assert isinstance(widget.filter_other_models_button, QPushButtonToggle)
        assert isinstance(widget.filter_other_families_button, QPushButtonToggle)

    def test_filter_buttons_have_tooltips(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that filter buttons have descriptive tooltips.
        """
        _ = ensure_google_icon_font
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Verify tooltips exist
        assert widget.filter_archived_button.toolTip() != ""
        assert widget.filter_other_models_button.toolTip() != ""
        assert widget.filter_other_families_button.toolTip() != ""
        assert widget.filter_rated_button.toolTip() != ""

    def test_filter_initial_state_archived_active(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that hide_archived filter is active by default.
        """
        _ = ensure_google_icon_font
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Hide archived should be active by default
        assert widget.completions_filter.hide_archived is True
        assert widget.filter_archived_button.is_toggled() is True


class TestCompletionsFilterFunctionality:
    """Test completions filter functionality."""

    def test_archived_filter_hides_archived(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test that archived filter hides archived completions.
        """
        _ = ensure_google_icon_font
        sample, prompt = create_test_sample(temp_dataset)
        active = create_test_completion_with_params(temp_dataset, prompt, completion_text="active", sha256="a" * 64)
        active.is_archived = False
        archived = create_test_completion_with_params(temp_dataset, prompt, completion_text="archived", sha256="b" * 64)
        archived.is_archived = True
        temp_dataset.commit()

        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        # Should show only active completion
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0] == active

        # Toggle to show archived
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()

        # Should now show both
        assert len(widget.completion_frames) == 2

    def test_model_filter_exact_match(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test filtering by exact model ID.
        """
        _ = ensure_google_icon_font
        sample, prompt = create_test_sample(temp_dataset)
        gemma_12b = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:12b", completion_text="gemma12",
                                                       sha256="a" * 64)
        _gemma_8b = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:8b", completion_text="gemma8",
                                                       sha256="b" * 64)
        temp_dataset.commit()

        # Get mock model from providers manager
        active_model = app_with_dataset.providers_manager.get_mock_model()
        # Override model_id for test
        active_model.model_id = "gemma3:12b"

        widget = WidgetSample(None, app_with_dataset, sample, active_model=active_model)
        widget.show()
        qt_app.processEvents()

        # Initially both shown (archived filter disabled by default)
        widget.filter_archived_button.clicked.emit()  # Disable archived filter
        qt_app.processEvents()
        assert len(widget.completion_frames) == 2

        # Enable exact model filter
        widget.filter_other_models_button.clicked.emit()
        qt_app.processEvents()

        # Should show only gemma3:12b
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0] == gemma_12b

    def test_family_filter(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test filtering by model family.
        """
        _ = ensure_google_icon_font
        sample, prompt = create_test_sample(temp_dataset)
        gemma = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:8b", completion_text="gemma", sha256="a" * 64)
        _llama = create_test_completion_with_params(temp_dataset, prompt, model_id="llama3:8b", completion_text="llama", sha256="b" * 64)
        temp_dataset.commit()

        # Get mock model from providers manager and override model_id
        active_model = app_with_dataset.providers_manager.get_mock_model()
        active_model.model_id = "gemma3:12b"

        widget = WidgetSample(None, app_with_dataset, sample, active_model=active_model)
        widget.show()
        qt_app.processEvents()

        # Disable archived filter
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()

        # Enable family filter
        widget.filter_other_families_button.clicked.emit()
        qt_app.processEvents()

        # Should show only gemma family
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0] == gemma

    def test_rating_filter(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test filtering by rating.
        """
        _ = ensure_google_icon_font
        facet = Facet.create(temp_dataset, "Test Facet", "Test", min_rating=7)
        sample, prompt = create_test_sample(temp_dataset)
        rated = create_test_completion_with_params(temp_dataset, prompt, completion_text="rated", sha256="a" * 64)
        unrated = create_test_completion_with_params(temp_dataset, prompt, completion_text="unrated", sha256="b" * 64)
        temp_dataset.commit()

        PromptCompletionRating.set_rating(temp_dataset, rated, facet, 4)

        widget = WidgetSample(None, app_with_dataset, sample, active_facet=facet)
        widget.show()
        qt_app.processEvents()

        # Disable archived filter
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()
        assert len(widget.completion_frames) == 2

        # Enable hide rated filter
        widget.filter_rated_button.clicked.emit()
        qt_app.processEvents()

        # Should show only unrated
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0] == unrated

    def test_truncation_filter(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test filtering by truncation status.
        """
        _ = ensure_google_icon_font
        sample, prompt = create_test_sample(temp_dataset)
        full = create_test_completion_with_params(temp_dataset, prompt, completion_text="full", sha256="a" * 64)
        full.is_truncated = False
        truncated = create_test_completion_with_params(temp_dataset, prompt, completion_text="truncated", sha256="b" * 64)
        truncated.is_truncated = True
        temp_dataset.commit()

        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        # Disable archived filter
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()
        assert len(widget.completion_frames) == 2

        # Enable hide truncated filter
        widget.filter_truncated_button.clicked.emit()
        qt_app.processEvents()

        # Should show only full
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0] == full

    def test_multiple_filters_and_logic(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test that multiple filters work with AND logic.
        """
        _ = ensure_google_icon_font
        facet = Facet.create(temp_dataset, "Test Facet", "Test", min_rating=7)
        sample, prompt = create_test_sample(temp_dataset)

        # Create various completions
        rated_full = create_test_completion_with_params(temp_dataset, prompt, completion_text="rated_full", sha256="a" * 64)
        rated_full.is_truncated = False
        rated_truncated = create_test_completion_with_params(temp_dataset, prompt, completion_text="rated_trunc", sha256="b" * 64)
        rated_truncated.is_truncated = True
        unrated_full = create_test_completion_with_params(temp_dataset, prompt, completion_text="unrated_full", sha256="c" * 64)
        unrated_full.is_truncated = False
        temp_dataset.commit()

        PromptCompletionRating.set_rating(temp_dataset, rated_full, facet, 4)
        PromptCompletionRating.set_rating(temp_dataset, rated_truncated, facet, 4)

        widget = WidgetSample(None, app_with_dataset, sample, active_facet=facet)
        widget.show()
        qt_app.processEvents()

        # Disable archived filter
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()
        assert len(widget.completion_frames) == 3

        # Enable hide rated filter
        widget.filter_rated_button.clicked.emit()
        qt_app.processEvents()
        assert len(widget.completion_frames) == 1

        # Also enable hide full filter
        widget.filter_full_button.clicked.emit()
        qt_app.processEvents()

        # Should show nothing (unrated_full is hidden by hide_full)
        assert len(widget.completion_frames) == 0


class TestCompletionsFilterPersistence:
    """Test filter state persistence."""

    def test_filter_state_saved_to_config(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that filter state is saved to configuration.
        """
        _ = ensure_google_icon_font
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Toggle some filters
        widget.filter_archived_button.clicked.emit()
        qt_app.processEvents()
        widget.filter_truncated_button.clicked.emit()
        qt_app.processEvents()

        # Check that changes are saved
        prefs = get_dataset_preferences(app_with_dataset, widget._dataset_pref_key())  # pylint: disable=protected-access
        filter_state = prefs.get("completions_filter")

        assert filter_state is not None
        assert isinstance(filter_state, dict)
        # After toggling, archived should be False (was True by default)
        assert filter_state.get("hide_archived") is False
        # After toggling, truncated should be True (was False by default)
        assert filter_state.get("hide_truncated") is True

    def test_filter_state_loaded_from_config(self, qt_app, app_with_dataset, temp_dataset, ensure_google_icon_font):
        """
        Test that filter state is loaded from configuration.
        """
        _ = ensure_google_icon_font

        # Get the actual dataset pref key
        dataset_key = str(Path(temp_dataset.db_path).resolve())

        # Set initial filter state in config
        update_dataset_preferences(app_with_dataset, dataset_key,
                                   {"completions_filter": {
                                       "hide_archived": False,
                                       "hide_truncated": True,
                                       "hide_other_models": True,
                                   }})

        # Create widget - should load saved filter state
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Verify filter state was loaded
        assert widget.completions_filter.hide_archived is False
        assert widget.completions_filter.hide_truncated is True
        assert widget.completions_filter.hide_other_models is True
        assert widget.filter_archived_button.is_toggled() is False
        assert widget.filter_truncated_button.is_toggled() is True
        assert widget.filter_other_models_button.is_toggled() is True
