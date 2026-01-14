"""
Test Export Wizard UI functionality with pytest-qt.
"""

import pathlib
from unittest.mock import Mock, patch

from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.gui.window_export_wizard import ExportWizard, ExportWorkerThread
from py_fade.controllers.export_controller import ExportController
from tests.helpers.export_wizard_helpers import create_test_template


def test_export_wizard_initialization(app_with_dataset, temp_dataset, qtbot):
    """
    Test that ExportWizard initializes correctly and displays proper UI.
    """
    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Test window properties
    assert wizard.windowTitle() == "Export Data Wizard"
    assert wizard.isModal()

    # Test initial step
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_TEMPLATE_SELECTION

    # Test navigation button states
    assert not wizard.back_button.isEnabled()
    assert wizard.next_button.text() == "Next →"

    # Test that UI components are created
    assert wizard.template_list is not None
    assert wizard.template_details is not None
    assert wizard.output_path_input is not None
    assert wizard.browse_button is not None


def test_export_wizard_template_selection_no_templates(app_with_dataset, temp_dataset, qtbot):
    """
    Test template selection when no templates are available.
    """
    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Should show disabled item when no templates
    assert wizard.template_list.count() == 1
    item = wizard.template_list.item(0)
    assert item.text() == "No export templates available"
    assert not item.flags() & item.flags().ItemIsEnabled

    # Next button should be disabled
    assert not wizard.next_button.isEnabled()


def test_export_wizard_template_selection_with_templates(app_with_dataset, temp_dataset, qtbot):
    """
    Test template selection when templates are available.
    """
    # Create a test template
    _facet, template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Should show the template
    assert wizard.template_list.count() == 1
    item = wizard.template_list.item(0)
    assert item.text() == "Test Template"

    # Next button should be disabled initially (no selection)
    assert not wizard.next_button.isEnabled()

    # Select the template
    wizard.template_list.setCurrentItem(item)
    qtbot.wait(100)  # Allow signal processing

    # Next button should now be enabled
    assert wizard.next_button.isEnabled()
    assert wizard.selected_template == template

    # Template details should be displayed
    details_text = wizard.template_details.toHtml()
    assert "Test Template" in details_text
    assert "Test template description" in details_text
    assert "SFT" in details_text


def test_export_wizard_navigation_forward(app_with_dataset, temp_dataset, qtbot):
    """
    Test forward navigation through wizard steps.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Step 1: Select template
    wizard.template_list.setCurrentRow(0)
    qtbot.wait(100)
    assert wizard.next_button.isEnabled()

    # Navigate to model selection
    wizard.next_button.click()  # Qt.LeftButton
    qtbot.wait(100)

    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_MODEL_SELECTION
    assert wizard.back_button.isEnabled()
    assert wizard.next_button.text() == "Next →"
    # Next button should be enabled if model is available (mock model should be there)
    if wizard.model_combo and wizard.model_combo.count() > 0:
        assert wizard.next_button.isEnabled()

    # Navigate to output selection
    wizard.next_button.click()  # Qt.LeftButton
    qtbot.wait(100)

    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_OUTPUT_SELECTION
    assert wizard.back_button.isEnabled()
    assert wizard.next_button.text() == "Export"
    assert not wizard.next_button.isEnabled()  # No output path selected yet


def test_export_wizard_navigation_backward(app_with_dataset, temp_dataset, qtbot):
    """
    Test backward navigation through wizard steps.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Navigate to step 2 (output selection)
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Go back to model selection
    wizard.back_button.click()  # Qt.LeftButton
    qtbot.wait(100)

    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_MODEL_SELECTION
    assert wizard.back_button.isEnabled()

    # Go back to template selection
    wizard.back_button.click()  # Qt.LeftButton
    qtbot.wait(100)

    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_TEMPLATE_SELECTION
    assert not wizard.back_button.isEnabled()


def test_export_wizard_output_path_selection(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test output path selection functionality.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Select template and navigate to output selection
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Test browsing for output path
    test_path = tmp_path / "test_export.jsonl"

    with patch('py_fade.gui.window_export_wizard.QFileDialog.getSaveFileName') as mock_dialog:
        mock_dialog.return_value = (str(test_path), "")

        wizard.browse_button.click()
        qtbot.wait(100)

    assert wizard.output_path == test_path
    assert str(test_path) in wizard.output_path_input.text()
    assert wizard.next_button.isEnabled()


def test_export_wizard_browse_without_template(app_with_dataset, temp_dataset, qtbot):
    """
    Test that browsing for output path without template selection shows warning.
    """
    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    with patch('py_fade.gui.window_export_wizard.QMessageBox.warning') as mock_warning:
        wizard.browse_button.click()
        qtbot.wait(100)

        mock_warning.assert_called_once()


def test_export_worker_thread(app_with_dataset, temp_dataset, qtbot):  # pylint: disable=unused-argument
    """
    Test the ExportWorkerThread functionality.
    """
    # Create a mock export controller
    mock_controller = Mock(spec=ExportController)
    mock_controller.run_export.return_value = 5

    # Create and test worker thread
    worker = ExportWorkerThread(mock_controller)

    # Set up signal capturing
    progress_signals = []
    completion_signals = []
    error_signals = []

    worker.progress_updated.connect(progress_signals.append)
    worker.export_completed.connect(completion_signals.append)
    worker.export_failed.connect(error_signals.append)

    # Run the worker
    worker.run()
    qtbot.wait(100)

    # Verify signals were emitted
    assert len(progress_signals) >= 2  # Should have at least start and end progress
    assert len(completion_signals) == 1
    assert completion_signals[0] == 5
    assert len(error_signals) == 0

    # Verify controller was called
    mock_controller.run_export.assert_called_once()


def test_export_worker_thread_error_handling(app_with_dataset, temp_dataset, qtbot):  # pylint: disable=unused-argument
    """
    Test ExportWorkerThread error handling.
    """
    # Create a mock export controller that raises an exception
    mock_controller = Mock(spec=ExportController)
    mock_controller.run_export.side_effect = ValueError("Test error")

    worker = ExportWorkerThread(mock_controller)

    # Set up signal capturing
    error_signals = []
    completion_signals = []

    worker.export_completed.connect(completion_signals.append)
    worker.export_failed.connect(error_signals.append)

    # Run the worker
    worker.run()
    qtbot.wait(100)

    # Verify error was captured
    assert len(error_signals) == 1
    assert "Test error" in error_signals[0]
    assert len(completion_signals) == 0


def test_export_wizard_full_flow_success(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test complete export wizard flow with successful export.
    """
    # Create a test template with sample data
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Step 1: Select template
    wizard.template_list.setCurrentRow(0)
    qtbot.wait(100)

    # Step 2: Select model (should be auto-selected if available)
    wizard.show_step(ExportWizard.STEP_MODEL_SELECTION)
    qtbot.wait(100)

    # Step 3: Set output path
    test_path = tmp_path / "test_export.jsonl"
    wizard.output_path = test_path
    wizard.output_path_input.setText(str(test_path))
    wizard.update_next_button()

    # Mock the export operation to avoid actual file operations
    with patch.object(wizard, 'export_controller') as mock_controller:
        mock_controller.run_export.return_value = 3

        # Navigate to progress step (this triggers export)
        wizard.show_step(ExportWizard.STEP_EXPORT_PROGRESS)
        qtbot.wait(100)

        # Simulate successful export
        wizard.export_completed(3)
        qtbot.wait(100)

    # Should be on results step
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_RESULTS
    assert wizard.next_button.text() == "Close"
    assert wizard.export_results.get("success") is True
    assert wizard.export_results.get("exported_count") == 3

    # Results should be displayed
    results_html = wizard.results_text.toHtml()
    assert "Export Successful!" in results_html
    assert "3" in results_html


def test_export_wizard_full_flow_failure(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test complete export wizard flow with export failure.
    """
    # Create a test template
    _facet, template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Set up wizard state
    wizard.selected_template = template
    test_path = tmp_path / "test_export.jsonl"
    wizard.output_path = test_path

    # Simulate export failure
    wizard.export_failed("Test export error")
    qtbot.wait(100)

    # Should be on results step showing failure
    assert wizard.content_stack.currentIndex() == ExportWizard.STEP_RESULTS
    assert wizard.export_results.get("success") is False
    assert wizard.export_results.get("error") == "Test export error"

    # Results should display error
    results_html = wizard.results_text.toHtml()
    assert "Export Failed" in results_html
    assert "Test export error" in results_html


def test_export_wizard_update_template_details(app_with_dataset, temp_dataset, qtbot):
    """
    Test template details update functionality.
    """
    # Create a test template with comprehensive data
    facet = Facet.create(temp_dataset, "Math Facet", "Mathematics evaluation")
    temp_dataset.commit()

    template = ExportTemplate.create(dataset=temp_dataset, name="Comprehensive Template", description="A detailed test template",
                                     model_families=["Gemma3", "Llama3"], training_type="SFT", output_format="JSONL (ShareGPT)", facets=[{
                                         "facet_id": facet.id,
                                         "limit_type": "count",
                                         "limit_value": 50,
                                         "order": "random"
                                     }])
    temp_dataset.commit()

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    wizard.selected_template = template
    wizard.update_template_details()

    details_html = wizard.template_details.toHtml()

    # Check all template information is displayed
    assert "Comprehensive Template" in details_html
    assert "A detailed test template" in details_html
    assert "SFT" in details_html
    assert "JSONL (ShareGPT)" in details_html
    assert "Gemma3, Llama3" in details_html
    assert f"Facet ID {facet.id}" in details_html


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


def test_export_wizard_uses_last_export_path(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test that ExportWizard uses last_export_path from config as default directory.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    # Set up last export path in config
    export_dir = tmp_path / "my_exports"
    export_dir.mkdir()
    app_with_dataset.config.last_export_path = str(export_dir)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Select template and navigate to output selection
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Mock QFileDialog to capture the default path
    with patch('py_fade.gui.window_export_wizard.QFileDialog.getSaveFileName') as mock_dialog:
        test_path = export_dir / "test_export.jsonl"
        mock_dialog.return_value = (str(test_path), "")

        wizard.browse_button.click()
        qtbot.wait(100)

        # Verify the default path passed to dialog includes the saved directory
        # Third argument (index 2) is the directory parameter which includes full path
        call_args = mock_dialog.call_args
        default_path_arg = call_args[0][2]  # Third positional argument is directory (full path)
        assert str(export_dir) in default_path_arg


def test_export_wizard_saves_export_path_to_config(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test that ExportWizard saves the selected export directory to config.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Select template and navigate to output selection
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Create test export directory
    export_dir = tmp_path / "new_export_location"
    export_dir.mkdir()
    test_path = export_dir / "test_export.jsonl"

    # Initially no last export path
    assert app_with_dataset.config.last_export_path is None

    # Browse and select path
    with patch('py_fade.gui.window_export_wizard.QFileDialog.getSaveFileName') as mock_dialog:
        mock_dialog.return_value = (str(test_path), "")

        wizard.browse_button.click()
        qtbot.wait(100)

    # Verify the directory was saved to config
    assert app_with_dataset.config.last_export_path == str(export_dir)


def test_export_wizard_handles_nonexistent_saved_path(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test that ExportWizard falls back to home directory if saved path doesn't exist.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    # Set last export path to a directory that doesn't exist
    nonexistent_dir = tmp_path / "nonexistent_directory"
    app_with_dataset.config.last_export_path = str(nonexistent_dir)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Select template and navigate to output selection
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Mock QFileDialog to capture the default path
    with patch('py_fade.gui.window_export_wizard.QFileDialog.getSaveFileName') as mock_dialog:
        mock_dialog.return_value = ("", "")  # User cancels

        wizard.browse_button.click()
        qtbot.wait(100)

        # Verify the default path falls back to home directory
        # Third argument (index 2) is the directory parameter which includes full path
        call_args = mock_dialog.call_args
        default_path_arg = call_args[0][2]
        # Should contain home directory, not the nonexistent one
        assert str(pathlib.Path.home()) in default_path_arg
        assert str(nonexistent_dir) not in default_path_arg


def test_export_wizard_updates_config_on_subsequent_exports(app_with_dataset, temp_dataset, qtbot, tmp_path):
    """
    Test that ExportWizard updates config when user selects a different directory.
    """
    # Create a test template
    _facet, _template = create_test_template(temp_dataset)

    # Set initial export path
    export_dir1 = tmp_path / "exports1"
    export_dir1.mkdir()
    app_with_dataset.config.last_export_path = str(export_dir1)

    wizard = ExportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Select template and navigate to output selection
    wizard.template_list.setCurrentRow(0)
    wizard.show_step(ExportWizard.STEP_OUTPUT_SELECTION)

    # Select a different directory
    export_dir2 = tmp_path / "exports2"
    export_dir2.mkdir()
    test_path = export_dir2 / "test_export.jsonl"

    with patch('py_fade.gui.window_export_wizard.QFileDialog.getSaveFileName') as mock_dialog:
        mock_dialog.return_value = (str(test_path), "")

        wizard.browse_button.click()
        qtbot.wait(100)

    # Verify config was updated to new directory
    assert app_with_dataset.config.last_export_path == str(export_dir2)
