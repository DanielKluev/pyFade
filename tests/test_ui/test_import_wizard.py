"""
Test Import Wizard UI functionality.
"""
from unittest.mock import Mock

from py_fade.gui.window_import_wizard import ImportWizard, ImportWorkerThread
from py_fade.controllers.import_controller import ImportController


def test_import_wizard_class_structure():
    """
    Test that ImportWizard has the expected class structure.
    """
    # Test step constants exist
    assert hasattr(ImportWizard, 'STEP_FILE_SELECTION')
    assert hasattr(ImportWizard, 'STEP_FORMAT_DETECTION')
    assert hasattr(ImportWizard, 'STEP_PREVIEW_FILTER')
    assert hasattr(ImportWizard, 'STEP_CONFIGURATION')
    assert hasattr(ImportWizard, 'STEP_CONFIRMATION')
    assert hasattr(ImportWizard, 'STEP_IMPORT_PROGRESS')
    assert hasattr(ImportWizard, 'STEP_RESULTS')
    
    # Test that step values are correct
    assert ImportWizard.STEP_FILE_SELECTION == 0
    assert ImportWizard.STEP_FORMAT_DETECTION == 1
    assert ImportWizard.STEP_PREVIEW_FILTER == 2
    assert ImportWizard.STEP_CONFIGURATION == 3
    assert ImportWizard.STEP_CONFIRMATION == 4
    assert ImportWizard.STEP_IMPORT_PROGRESS == 5
    assert ImportWizard.STEP_RESULTS == 6


def test_import_worker_thread_signals():
    """
    Test that ImportWorkerThread has the expected signals.
    """
    # Create a mock import controller
    mock_controller = Mock(spec=ImportController)
    worker = ImportWorkerThread(mock_controller)
    
    # Test that signals exist
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'import_completed')
    assert hasattr(worker, 'import_failed')
    
    # Test that worker stores the controller
    assert worker.import_controller == mock_controller


def test_import_wizard_validation_methods():
    """
    Test that ImportWizard has all expected validation methods.
    """
    # Test that validation methods exist
    assert hasattr(ImportWizard, 'validate_file_selection')
    assert hasattr(ImportWizard, 'validate_format_detection')
    assert hasattr(ImportWizard, 'validate_preview_filter')
    assert hasattr(ImportWizard, 'validate_configuration')
    
    # Test that navigation methods exist
    assert hasattr(ImportWizard, 'go_back')
    assert hasattr(ImportWizard, 'go_next')
    assert hasattr(ImportWizard, 'show_step')
    
    # Test that update methods exist
    assert hasattr(ImportWizard, 'update_format_detection')
    assert hasattr(ImportWizard, 'update_preview')
    assert hasattr(ImportWizard, 'update_confirmation')


def test_import_wizard_step_widget_creation():
    """
    Test that ImportWizard has methods to create all step widgets.
    """
    # Test that step widget creation methods exist
    assert hasattr(ImportWizard, 'create_file_selection_widget')
    assert hasattr(ImportWizard, 'create_format_detection_widget')
    assert hasattr(ImportWizard, 'create_preview_filter_widget')
    assert hasattr(ImportWizard, 'create_configuration_widget')
    assert hasattr(ImportWizard, 'create_confirmation_widget')
    assert hasattr(ImportWizard, 'create_progress_widget')
    assert hasattr(ImportWizard, 'create_results_widget')


def test_import_wizard_file_operations():
    """
    Test that ImportWizard has file operation methods.
    """
    # Test that file operation methods exist
    assert hasattr(ImportWizard, 'add_files')
    assert hasattr(ImportWizard, 'remove_selected_files')
    assert hasattr(ImportWizard, 'load_facets')


def test_import_wizard_import_operations():
    """
    Test that ImportWizard has import operation methods.
    """
    # Test that import operation methods exist
    assert hasattr(ImportWizard, 'start_import')
    assert hasattr(ImportWizard, 'update_progress')
    assert hasattr(ImportWizard, 'import_completed')
    assert hasattr(ImportWizard, 'import_failed')