"""
Test Export Wizard model selection functionality.

Tests the new model selection step and its integration with export controller.
"""

from unittest.mock import Mock, patch
import pathlib
import tempfile

from py_fade.gui.window_export_wizard import ExportWizard
from py_fade.controllers.export_controller import ExportController
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from tests.helpers.export_wizard_helpers import create_test_template
from tests.helpers.data_helpers import create_completion_with_rating_and_logprobs


def test_export_wizard_model_selection_step_exists(app_with_dataset, temp_dataset, qtbot):
    """
    Test that model selection step is present in the wizard.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Verify model selection step exists
    assert hasattr(wizard, 'STEP_MODEL_SELECTION')
    assert wizard.STEP_MODEL_SELECTION == 1

    # Verify model selection widget is created
    assert wizard.model_combo is not None


def test_export_wizard_model_selection_populated(app_with_dataset, temp_dataset, qtbot):
    """
    Test that model selection combobox is populated with available models.
    """
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Navigate to model selection step
    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)

    # Should have at least mock model
    assert wizard.model_combo.count() > 0

    # Mock model should be present
    model_ids = [wizard.model_combo.itemText(i) for i in range(wizard.model_combo.count())]
    assert "mock-echo-model" in model_ids


def test_export_wizard_model_selection_auto_selected(app_with_dataset, temp_dataset, qtbot):
    """
    Test that first model is auto-selected when navigating to model selection step.
    """
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Navigate to model selection step
    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)

    # First model should be selected
    if wizard.model_combo.count() > 0:
        assert wizard.model_combo.currentIndex() == 0
        assert wizard.selected_model_id is not None
        assert wizard.next_button.isEnabled()


def test_export_wizard_model_selection_changed(app_with_dataset, temp_dataset, qtbot):
    """
    Test model selection change handler.
    """
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)

    # Change model selection
    if wizard.model_combo.count() > 0:
        original_model = wizard.model_combo.currentText()
        wizard.model_combo.setCurrentIndex(0)
        qtbot.wait(100)

        # Selected model should be updated
        assert wizard.selected_model_id == original_model


def test_export_wizard_passes_model_to_controller(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test that selected model is passed to ExportController.
    """
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Set up wizard state
    wizard.selected_template = _template
    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)
    wizard.selected_model_id = "mock-echo-model"
    test_path = tmp_path / "test_export.jsonl"
    wizard.output_path = test_path

    # Mock ExportController constructor to capture arguments
    with patch('py_fade.controllers.export_controller.ExportController') as mock_controller_cls:
        mock_instance = Mock(spec=ExportController)
        mock_instance.export_results = None
        mock_instance.run_export.return_value = 1
        mock_controller_cls.return_value = mock_instance

        # Trigger export (this will call start_export internally)
        # We need to trigger it but not wait for the worker thread
        wizard.start_export()
        qtbot.wait(100)

        # Verify controller was created with correct model_id
        mock_controller_cls.assert_called_once()
        call_args = mock_controller_cls.call_args
        assert call_args[0][0] == app_with_dataset  # app
        assert call_args[0][1] == temp_dataset  # dataset
        assert call_args[0][2] == _template  # template
        assert call_args[0][3] == "mock-echo-model"  # target_model_id


def test_export_controller_uses_target_model_id(app_with_dataset, temp_dataset):
    """
    Test that ExportController uses the provided target_model_id for logprobs validation.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with completion
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "test_group")
    temp_dataset.commit()

    # Create completion with good logprobs for mock-echo-model
    create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Test completion", mapped_model.model_id, facet, rating=8,
                                               min_logprob=-0.4, avg_logprob=-0.2)

    # Create export template
    from py_fade.dataset.export_template import ExportTemplate  # pylint: disable=import-outside-toplevel
    template = ExportTemplate.create(
        temp_dataset, name="Test Template", description="Test template", training_type="SFT", output_format="JSONL (ShareGPT)",
        model_families=["Llama3"], facets=[{
            "facet_id": facet.id,
            "limit_type": "percentage",
            "limit_value": 100,
            "order": "random",
            "min_rating": None,
            "min_logprob": None,
            "avg_logprob": None,
        }])
    temp_dataset.commit()

    # Export with target_model_id specified
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        exported_count = export_controller.run_export()

        # Should successfully export with specified model
        assert exported_count == 1
        assert export_controller.target_model_id == mapped_model.model_id

    finally:
        temp_path.unlink(missing_ok=True)


def test_export_controller_fallback_without_target_model(app_with_dataset, temp_dataset):
    """
    Test that ExportController falls back to first available model when target_model_id is None.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=7)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with completion
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "test_group")
    temp_dataset.commit()

    create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Test completion", mapped_model.model_id, facet, rating=8,
                                               min_logprob=-0.4, avg_logprob=-0.2)

    # Create export template
    from py_fade.dataset.export_template import ExportTemplate  # pylint: disable=import-outside-toplevel
    template = ExportTemplate.create(temp_dataset, name="Test Template", description="Test template", training_type="SFT",
                                     output_format="JSONL (ShareGPT)", model_families=["Llama3"], facets=[{
                                         "facet_id": facet.id,
                                         "limit_type": "percentage",
                                         "limit_value": 100,
                                         "order": "random",
                                     }])
    temp_dataset.commit()

    # Export without target_model_id (should fall back)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=None)
        export_controller.set_output_path(temp_path)
        exported_count = export_controller.run_export()

        # Should successfully export with fallback model
        assert exported_count == 1
        # target_model_id should remain None (fallback is used internally)
        assert export_controller.target_model_id is None

    finally:
        temp_path.unlink(missing_ok=True)


def test_export_wizard_model_selection_next_button_state(app_with_dataset, temp_dataset, qtbot):
    """
    Test that next button is correctly enabled/disabled based on model selection.
    """
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Navigate to model selection step
    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)

    # Next button should be enabled if model is available
    if wizard.model_combo.count() > 0:
        assert wizard.next_button.isEnabled()
    else:
        # If no models available, next button should be disabled
        assert not wizard.next_button.isEnabled()


def test_export_wizard_complete_flow_with_model_selection(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test complete wizard flow including model selection.
    """
    # Create test data
    facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=5)
    temp_dataset.commit()

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    prompt_rev = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "test_group")
    temp_dataset.commit()

    create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Test completion", mapped_model.model_id, facet, rating=8,
                                               min_logprob=-0.4, avg_logprob=-0.2)

    # Create template
    from py_fade.dataset.export_template import ExportTemplate  # pylint: disable=import-outside-toplevel
    template = ExportTemplate.create(temp_dataset, name="Test Template", description="Test template", training_type="SFT",
                                     output_format="JSONL (ShareGPT)", model_families=["Llama3"], facets=[{
                                         "facet_id": facet.id,
                                         "limit_type": "percentage",
                                         "limit_value": 100,
                                         "order": "random",
                                     }])
    temp_dataset.commit()

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Step 1: Select template
    wizard.template_list.setCurrentRow(0)
    qtbot.wait(100)
    assert wizard.selected_template == template
    assert wizard.next_button.isEnabled()

    # Step 2: Model selection (should be auto-selected)
    wizard.next_button.click()
    qtbot.wait(100)
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_MODEL_SELECTION
    assert wizard.selected_model_id is not None
    assert wizard.next_button.isEnabled()

    # Step 3: Output selection
    wizard.next_button.click()
    qtbot.wait(100)
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_OUTPUT_SELECTION

    test_path = tmp_path / "test_export.jsonl"
    wizard.output_path = test_path
    wizard.output_path_input.setText(str(test_path))
    wizard.update_next_button()
    assert wizard.next_button.isEnabled()

    # Export step - mock the controller
    with patch.object(wizard, 'export_controller') as mock_controller:
        mock_controller.run_export.return_value = 1

        wizard.next_button.click()
        qtbot.wait(100)

        # Simulate success
        wizard.export_completed(1)
        qtbot.wait(100)

    # Should be on results step
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_RESULTS
    assert wizard.export_results.get("success") is True
