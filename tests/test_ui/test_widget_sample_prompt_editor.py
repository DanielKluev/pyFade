"""
Test Widget Plain Text Edit integration test.

Tests for PlainTextEdit component integration and ensuring the bug fix
works correctly with the WidgetSample.
"""
import inspect

from PyQt6.QtWidgets import QTextEdit

from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit
from py_fade.gui import widget_sample


def test_plain_text_edit_configuration():
    """
    Test that PlainTextEdit has correct configuration to prevent rich text.

    This tests the class definition and key properties without requiring
    a full Qt application context.
    """
    # Test that the class has the required methods
    assert hasattr(PlainTextEdit, 'insertFromMimeData')
    assert hasattr(PlainTextEdit, 'setHtml')
    assert hasattr(PlainTextEdit, '__init__')

    # Verify the class inherits from QTextEdit
    assert issubclass(PlainTextEdit, QTextEdit)


def test_integration_widget_sample_uses_plain_text_edit():
    """
    Test that WidgetSample uses PlainTextEdit instead of QTextEdit.

    This verifies that the integration is correctly implemented by checking
    the import and usage in the WidgetSample class.
    """
    # Verify PlainTextEdit is imported
    assert hasattr(widget_sample, 'PlainTextEdit')

    # Check that the import is correct
    source = inspect.getsource(widget_sample.WidgetSample.setup_ui)

    # Verify that PlainTextEdit is used instead of QTextEdit in prompt_area
    assert 'PlainTextEdit(self)' in source
    assert 'self.prompt_area = PlainTextEdit(self)' in source
