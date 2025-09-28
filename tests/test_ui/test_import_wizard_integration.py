"""
Test Import Wizard menu integration with pytest-qt.
"""

from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from py_fade.gui.window_import_wizard import ImportWizard, ImportWorkerThread


def test_import_wizard_menu_integration(app_with_dataset, temp_dataset, qtbot, ensure_google_icon_font):
    """
    Test that the Import Data menu item is properly integrated into the dataset top widget.
    """
    # Create the dataset top widget
    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(widget)

    # Verify the menu item exists
    assert widget.action_import_wizard is not None

    # Verify the menu item has the correct text
    assert widget.action_import_wizard.text() == "Import Data…"

    # Verify the menu item is in the file menu
    assert widget.action_import_wizard.parent() == widget.file_menu

    # Verify the handler is connected (we can test the method exists)
    assert hasattr(widget, '_handle_import_wizard')
    assert callable(widget._handle_import_wizard)


def test_import_wizard_instantiation_from_menu(app_with_dataset, temp_dataset, qtbot):
    """
    Test that ImportWizard can be instantiated and shown properly.
    """
    # Create wizard directly (as the menu handler would)
    wizard = ImportWizard(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(wizard)

    # Test basic properties
    assert wizard.windowTitle() == "Import Data Wizard"
    assert wizard.isModal()

    # Test that it has the expected step widgets
    assert wizard.content_stack.count() == 7  # Should have 7 steps

    # Test initial step display
    assert wizard.content_stack.currentIndex() == ImportWizard.STEP_FILE_SELECTION


def test_import_worker_thread_creation():
    """
    Test that ImportWorkerThread can be created and has expected interface.
    """
    from py_fade.controllers.import_controller import ImportController

    # Create import controller and worker
    import_controller = ImportController(None, None)
    worker = ImportWorkerThread(import_controller)

    assert worker is not None
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'import_completed')
    assert hasattr(worker, 'import_failed')
    assert hasattr(worker, 'run')
    assert worker.import_controller == import_controller