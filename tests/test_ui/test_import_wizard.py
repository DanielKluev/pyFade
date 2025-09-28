"""
Test Import Wizard UI functionality with pytest-qt.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from py_fade.dataset.facet import Facet
from py_fade.gui.window_import_wizard import ImportWizard, ImportWorkerThread
from py_fade.controllers.import_controller import ImportController


def test_import_wizard_initialization(app_with_dataset, temp_dataset, qt_app):
    """
    Test that ImportWizard initializes correctly and displays proper UI.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Test window properties
    assert wizard.windowTitle() == "Import Data Wizard"
    assert wizard.isModal()

    # Test initial step
    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FILE_SELECTION

    # Test navigation button states
    assert not wizard.back_button.isEnabled()
    assert wizard.next_button.isEnabled()
    assert wizard.next_button.text() == "Next →"

    # Test that UI components are created
    assert wizard.file_list is not None
    assert wizard.add_file_button is not None
    assert wizard.remove_file_button is not None

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_file_selection_interaction(app_with_dataset, temp_dataset, qt_app):
    """
    Test file selection step UI interactions.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Initially no files should be selected
    assert wizard.file_list.count() == 0
    assert len(wizard.selected_files) == 0

    # Test that Next button is disabled when no files selected (validation should prevent advance)
    wizard.go_next()
    qt_app.processEvents()
    # Should still be on file selection step due to validation
    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FILE_SELECTION

    # Simulate adding a file
    test_file = Path("/tmp/test_file.json")
    wizard.selected_files.append(test_file)

    # Simulate UI update for added file
    from PyQt6.QtWidgets import QListWidgetItem
    from PyQt6.QtCore import Qt
    item = QListWidgetItem(str(test_file.name))
    item.setData(Qt.ItemDataRole.UserRole, test_file)
    wizard.file_list.addItem(item)
    qt_app.processEvents()

    # Now should be able to advance
    assert wizard.file_list.count() == 1

    # Test file removal
    wizard.file_list.setCurrentRow(0)
    wizard.remove_selected_files()
    qt_app.processEvents()

    assert wizard.file_list.count() == 0
    assert len(wizard.selected_files) == 0

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_navigation_flow(app_with_dataset, temp_dataset, qt_app):
    """
    Test wizard step navigation and button state changes.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Start at file selection
    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FILE_SELECTION
    assert not wizard.back_button.isEnabled()

    # Add a file to enable navigation
    test_file = Path("/tmp/test.json")
    wizard.selected_files.append(test_file)

    # Navigate to format detection step
    wizard.show_step(ImportWizard.STEP_FORMAT_DETECTION)
    qt_app.processEvents()

    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FORMAT_DETECTION
    assert wizard.back_button.isEnabled()
    assert wizard.next_button.text() == "Next →"

    # Navigate back
    wizard.go_back()
    qt_app.processEvents()

    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FILE_SELECTION
    assert not wizard.back_button.isEnabled()

    # Navigate to confirmation step
    wizard.show_step(ImportWizard.STEP_CONFIRMATION)
    qt_app.processEvents()

    assert wizard.next_button.text() == "Start Import"

    # Navigate to results step
    wizard.show_step(ImportWizard.STEP_RESULTS)
    qt_app.processEvents()

    assert wizard.next_button.text() == "Close"
    assert not wizard.cancel_button.isVisible()

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_configuration_step(app_with_dataset, temp_dataset, qt_app):
    """
    Test configuration step UI components and interactions.
    """
    # Create a test facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()

    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Navigate to configuration step
    wizard.show_step(ImportWizard.STEP_CONFIGURATION)
    qt_app.processEvents()

    # Test facet combo is populated
    assert wizard.facet_combo.count() > 1  # Should have "None" + created facets

    # Test setting facet selection
    wizard.facet_combo.setCurrentIndex(1)  # Select first real facet
    qt_app.processEvents()

    # Test rating spin boxes
    wizard.correct_rating_spin.setValue(9)
    wizard.incorrect_rating_spin.setValue(1)
    wizard.chosen_rating_spin.setValue(8)
    wizard.rejected_rating_spin.setValue(2)
    qt_app.processEvents()

    assert wizard.correct_rating_spin.value() == 9
    assert wizard.incorrect_rating_spin.value() == 1

    # Test group path field
    wizard.group_path_edit.setText("Test Group Path")
    qt_app.processEvents()

    assert wizard.group_path_edit.text() == "Test Group Path"

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_format_detection_display(app_with_dataset, temp_dataset, qt_app):
    """
    Test format detection step UI updates.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Add test files
    test_files = [Path("test1.json"), Path("test2.json")]
    wizard.selected_files = test_files

    # Navigate to format detection step
    wizard.show_step(ImportWizard.STEP_FORMAT_DETECTION)
    qt_app.processEvents()

    # Format table should have rows for each file
    assert wizard.format_table.rowCount() == len(test_files)
    assert len(wizard.detected_formats) == len(test_files)

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_preview_filter_controls(app_with_dataset, temp_dataset, qt_app):
    """
    Test preview and filter step UI controls.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Navigate to preview/filter step
    wizard.show_step(ImportWizard.STEP_PREVIEW_FILTER)
    qt_app.processEvents()

    # Test filter controls
    assert wizard.paired_filter_checkbox is not None
    assert wizard.filter_type_combo is not None

    # Test checkbox interaction
    wizard.paired_filter_checkbox.setChecked(True)
    qt_app.processEvents()
    assert wizard.paired_filter_checkbox.isChecked()

    wizard.paired_filter_checkbox.setChecked(False)
    qt_app.processEvents()
    assert not wizard.paired_filter_checkbox.isChecked()

    # Test filter type combo
    wizard.filter_type_combo.setCurrentText("shared_success")
    qt_app.processEvents()
    assert wizard.filter_type_combo.currentText() == "shared_success"

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_confirmation_summary(app_with_dataset, temp_dataset, qt_app):
    """
    Test confirmation step summary display.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Set up some test data
    wizard.selected_files = [Path("test.json")]
    wizard.import_controller.active_records = [Mock()] * 3  # 3 mock records

    # Navigate to confirmation step
    wizard.show_step(ImportWizard.STEP_CONFIRMATION)
    qt_app.processEvents()

    # Summary should be populated
    summary_text = wizard.summary_text.toPlainText()
    assert "FILES TO IMPORT:" in summary_text
    assert "TOTAL RECORDS: 3" in summary_text
    assert "CONFIGURATION:" in summary_text

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_progress_display(app_with_dataset, temp_dataset, qt_app):
    """
    Test progress step UI components.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Navigate to progress step
    wizard.show_step(ImportWizard.STEP_IMPORT_PROGRESS)
    qt_app.processEvents()

    # Test progress components exist
    assert wizard.progress_bar is not None
    assert wizard.progress_status_label is not None
    assert wizard.progress_details is not None

    # Test progress updates
    wizard.update_progress(50, "Testing progress")
    qt_app.processEvents()

    assert wizard.progress_bar.value() == 50
    assert wizard.progress_status_label.text() == "Testing progress"
    assert "Testing progress" in wizard.progress_details.toPlainText()

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_results_display(app_with_dataset, temp_dataset, qt_app):
    """
    Test results step UI components and success/failure display.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Test successful import display
    wizard.import_completed(5)
    qt_app.processEvents()

    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_RESULTS
    assert "✓" in wizard.results_label.text()
    assert "Successfully" in wizard.results_label.text()
    assert "5" in wizard.results_text.toPlainText()

    wizard.close()
    qt_app.processEvents()


def test_import_wizard_results_display_failure(app_with_dataset, temp_dataset, qt_app):
    """
    Test results step failure display.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Test failed import display
    wizard.import_failed("Test error message")
    qt_app.processEvents()

    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_RESULTS
    assert "✗" in wizard.results_label.text()
    assert "Failed" in wizard.results_label.text()
    assert "Test error message" in wizard.results_text.toPlainText()

    wizard.close()
    qt_app.processEvents()


def test_import_worker_thread_functionality(app_with_dataset, temp_dataset, qt_app):
    """
    Test ImportWorkerThread signal emission and functionality.
    """
    # Create worker with empty controller
    import_controller = ImportController(app_with_dataset, temp_dataset)
    worker = ImportWorkerThread(import_controller)

    # Capture emitted signals
    progress_signals = []
    completion_signals = []
    failure_signals = []

    worker.progress_updated.connect(lambda p, s: progress_signals.append((p, s)))
    worker.import_completed.connect(lambda c: completion_signals.append(c))
    worker.import_failed.connect(lambda e: failure_signals.append(e))

    # Run the worker
    worker.start()
    worker.wait(2000)  # Wait up to 2 seconds

    # Should have received progress updates and completion
    assert len(progress_signals) > 0
    assert len(completion_signals) == 1
    assert len(failure_signals) == 0

    # Check final completion
    assert completion_signals[0] == 0  # No records in empty controller

    # Check that progress included completion message
    progress_messages = [msg for _, msg in progress_signals]
    assert any("completed" in msg.lower() for msg in progress_messages)


def test_import_wizard_validation_integration(app_with_dataset, temp_dataset, qt_app):
    """
    Test that wizard validation methods work correctly in UI context.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Test file selection validation
    assert not wizard.validate_file_selection()

    # Add a file and test validation passes
    wizard.selected_files.append(Path("test.json"))
    assert wizard.validate_file_selection()

    # Test configuration validation (should pass with no facet)
    assert wizard.validate_configuration()

    # Test preview filter validation (should pass without paired comparison)
    wizard.paired_filter_checkbox.setChecked(False)
    assert wizard.validate_preview_filter()

    wizard.close()
    qt_app.processEvents()


@patch('py_fade.gui.window_import_wizard.QMessageBox.critical')
def test_import_wizard_error_handling_ui(mock_critical, app_with_dataset, temp_dataset, qt_app):
    """
    Test that error dialogs are shown properly in UI error scenarios.
    """
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Test error handling in format detection
    with patch.object(wizard.import_controller, 'detect_format', side_effect=Exception("Test error")):
        wizard.selected_files = [Path("test.json")]
        wizard.update_format_detection()
        qt_app.processEvents()

        # Should have "error" in detected formats
        assert len(wizard.detected_formats) > 0
        assert "error" in wizard.detected_formats

    # Test error handling in preview
    with patch.object(wizard.import_controller, 'load_sources', side_effect=Exception("Load error")):
        wizard.update_preview()
        qt_app.processEvents()

        # Should have shown error dialog
        mock_critical.assert_called()

    wizard.close()
    qt_app.processEvents()