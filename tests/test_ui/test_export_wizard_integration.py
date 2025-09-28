"""
Test Export Wizard integration with WidgetDatasetTop.
"""

from unittest.mock import patch
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.gui.widget_dataset_top import WidgetDatasetTop


def test_export_wizard_menu_action(app_with_dataset, temp_dataset, qtbot):
    """
    Test that the Export Wizard menu action in WidgetDatasetTop works correctly.
    """
    # Create a facet and export template for testing
    facet = Facet.create(temp_dataset, "Test Facet", "Test facet description")
    temp_dataset.commit()

    template = ExportTemplate.create(
        dataset=temp_dataset,
        name="Test Template",
        description="Test template description", 
        model_families=["Gemma3"],
        training_type="SFT",
        output_format="JSONL (ShareGPT)",
        facets=[{"facet_id": facet.id, "limit_type": "count", "limit_value": 100, "order": "random"}]
    )
    temp_dataset.commit()

    # Create the dataset widget
    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(widget)
    
    # Check that the action exists and is enabled
    assert widget.action_export_wizard is not None
    assert widget.action_export_wizard.isEnabled()
    
    # Mock the ExportWizard dialog to avoid actually opening it
    with patch('py_fade.gui.widget_dataset_top.ExportWizard') as mock_wizard_class:
        mock_wizard = mock_wizard_class.return_value
        mock_wizard.exec.return_value = mock_wizard.DialogCode.Accepted
        
        # Trigger the action
        widget.action_export_wizard.triggered.emit(False)
        qtbot.wait(100)
        
        # Verify the wizard was created with correct parameters
        mock_wizard_class.assert_called_once_with(widget, app_with_dataset, temp_dataset)
        mock_wizard.exec.assert_called_once()


def test_export_wizard_menu_refresh_state(app_with_dataset, temp_dataset, qtbot):
    """
    Test that the Export Wizard action state is properly refreshed.
    """
    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(widget)
    
    # The export wizard action should always be enabled
    widget._refresh_menu_state()
    
    assert widget.action_export_wizard is not None
    assert widget.action_export_wizard.isEnabled()


def test_export_wizard_handler_method(app_with_dataset, temp_dataset, qtbot):
    """
    Test the _handle_export_wizard method directly.
    """
    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qtbot.addWidget(widget)
    
    # Mock the ExportWizard to test the handler
    with patch('py_fade.gui.widget_dataset_top.ExportWizard') as mock_wizard_class:
        mock_wizard = mock_wizard_class.return_value
        mock_wizard.exec.return_value = mock_wizard.DialogCode.Accepted
        
        # Call the handler method
        widget._handle_export_wizard()
        qtbot.wait(100)
        
        # Verify the wizard was created and executed
        mock_wizard_class.assert_called_once_with(widget, app_with_dataset, temp_dataset)
        mock_wizard.exec.assert_called_once()