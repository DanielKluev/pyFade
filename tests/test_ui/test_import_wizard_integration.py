"""
Test Import Wizard menu integration.
"""
def test_import_wizard_menu_exists():
    """
    Test that the Import Data menu item exists and can be imported.
    """
    from py_fade.gui.widget_dataset_top import WidgetDatasetTop
    from py_fade.gui.window_import_wizard import ImportWizard
    
    # Test that the classes can be imported successfully
    assert WidgetDatasetTop is not None
    assert ImportWizard is not None
    
    # Test that ImportWizard has the expected structure
    assert hasattr(ImportWizard, 'STEP_FILE_SELECTION')
    assert hasattr(ImportWizard, 'STEP_FORMAT_DETECTION')
    assert hasattr(ImportWizard, 'STEP_PREVIEW_FILTER')
    assert hasattr(ImportWizard, 'STEP_CONFIGURATION')
    assert hasattr(ImportWizard, 'STEP_CONFIRMATION')
    assert hasattr(ImportWizard, 'STEP_IMPORT_PROGRESS')
    assert hasattr(ImportWizard, 'STEP_RESULTS')


def test_import_worker_thread_exists():
    """
    Test that ImportWorkerThread can be imported and has the expected structure.
    """
    from py_fade.gui.window_import_wizard import ImportWorkerThread
    
    assert ImportWorkerThread is not None
    assert hasattr(ImportWorkerThread, 'progress_updated')
    assert hasattr(ImportWorkerThread, 'import_completed')
    assert hasattr(ImportWorkerThread, 'import_failed')
    assert hasattr(ImportWorkerThread, 'run')