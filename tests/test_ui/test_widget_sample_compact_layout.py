"""
Test Widget Sample Compact Layout Implementation.

Tests for the compactified control panel in WidgetSample ensuring proper
layout and functionality while maintaining user experience.
"""
from PyQt6.QtWidgets import QHBoxLayout, QCheckBox, QLineEdit, QSpinBox, QFrame

from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon


class TestWidgetSampleCompactLayout:
    """Test compact layout implementation for WidgetSample control panel."""

    def test_controls_layout_structure(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that the controls layout has the expected compact structure.
        
        Validates:
        - Label and field pairs are on same row
        - Context length and max tokens are on same row
        - Buttons are icon-only and on same row  
        - Show archived control is in controls panel, not completions panel
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Find the controls frame and its layout more robustly
        controls_frame = None

        # Look for QFrame that contains our control widgets (id_field) but is not a QSplitter
        frames = widget.findChildren(QFrame)
        for frame in frames:
            # Skip QSplitter objects as they don't have our controls
            if frame.__class__.__name__ == 'QSplitter':
                continue
            lineedits = frame.findChildren(QLineEdit)
            if widget.id_field in lineedits:
                controls_frame = frame
                break

        if not controls_frame:
            # Fallback: find parent widget traversing up from id_field
            parent = widget.id_field.parent()
            while parent and parent != widget:
                if isinstance(parent, QFrame) and parent.__class__.__name__ != 'QSplitter':
                    controls_frame = parent
                    break
                parent = parent.parent()

        assert controls_frame is not None, "Controls frame should be found. Widget type needed: QFrame (not QSplitter)"
        controls_layout = controls_frame.layout()
        assert controls_layout is not None, "Controls frame should have a layout"

        # Check that show_archived_checkbox is in controls panel, not completions
        show_archived_in_controls = any(
            isinstance(child, QCheckBox) and "archived" in child.text().lower() for child in controls_frame.findChildren(QCheckBox))
        assert show_archived_in_controls, "Show archived checkbox should be in controls panel"

    def test_horizontal_layouts_for_fields(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that label-field pairs use horizontal layouts for compactness.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Check that we have horizontal layouts containing labels and fields
        horizontal_layouts = widget.findChildren(QHBoxLayout)

        # Should have at least one horizontal layout for combined context/max tokens
        assert len(horizontal_layouts) > 0, "Should have horizontal layouts for compact design"

        # Check for context length and max tokens in same layout
        context_max_tokens_together = False
        for h_layout in horizontal_layouts:
            spinboxes_in_layout = []
            for i in range(h_layout.count()):
                item = h_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QSpinBox):
                    spinboxes_in_layout.append(item.widget())

            if len(spinboxes_in_layout) >= 2:
                # Check if these are our context length and max tokens fields
                if (widget.context_length_field in spinboxes_in_layout and widget.max_tokens_field in spinboxes_in_layout):
                    context_max_tokens_together = True
                    break

        assert context_max_tokens_together, "Context length and max tokens should be in same horizontal layout"

    def test_icon_only_buttons_with_tooltips(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that action buttons in WidgetSample controls are icon-only with informative tooltips.

        Note: NewCompletionFrame buttons are excluded as they use text labels for clarity.
        """
        # Import here to avoid circular imports
        from py_fade.gui.widget_new_completion import NewCompletionFrame  # pylint: disable=import-outside-toplevel

        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Check for QPushButtonWithIcon instances, excluding NewCompletionFrame buttons
        icon_buttons = widget.findChildren(QPushButtonWithIcon)

        # Filter out NewCompletionFrame buttons
        widget_sample_buttons = [btn for btn in icon_buttons if not isinstance(btn.parent(), NewCompletionFrame)]

        # Should have at least 3 icon buttons (save, copy, beam search) in WidgetSample controls
        assert len(widget_sample_buttons) >= 3, "Should have at least 3 icon-only buttons in WidgetSample controls"

        # Check that buttons have tooltips and no text (or minimal text)
        for button in widget_sample_buttons:
            # Icon buttons should have tooltips
            assert button.toolTip(), f"Button {button} should have a tooltip"

            # Icon buttons should have minimal or no text
            button_text = button.text().strip()
            assert len(button_text) <= 2, f"Button should be icon-only or have minimal text, got: '{button_text}'"

    def test_buttons_in_horizontal_layout(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that action buttons are arranged in a single horizontal row.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Find horizontal layout containing multiple buttons
        horizontal_layouts = widget.findChildren(QHBoxLayout)
        buttons_layout_found = False

        for h_layout in horizontal_layouts:
            button_count = 0
            for i in range(h_layout.count()):
                item = h_layout.itemAt(i)
                if (item and item.widget() and (isinstance(item.widget(), QPushButtonWithIcon) or hasattr(item.widget(), 'clicked'))):
                    button_count += 1

            if button_count >= 3:  # Should have save, copy, beam search buttons
                buttons_layout_found = True
                break

        assert buttons_layout_found, "Action buttons should be in a horizontal layout"

    def test_widget_functionality_preserved(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that all original widget functionality is preserved after layout changes.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Check that all essential widgets are still present and functional
        assert widget.id_field is not None, "ID field should be present"
        assert widget.title_field is not None, "Title field should be present"
        assert widget.group_field is not None, "Group field should be present"
        assert widget.context_length_field is not None, "Context length field should be present"
        assert widget.max_tokens_field is not None, "Max tokens field should be present"
        assert widget.save_button is not None, "Save button should be present"
        assert widget.copy_button is not None, "Copy button should be present"
        assert widget.beam_search_button is not None, "Beam search button should be present"
        assert widget.show_archived_checkbox is not None, "Show archived checkbox should be present"

        # Test that fields can be modified
        widget.title_field.setText("Test Title")
        assert widget.title_field.text() == "Test Title", "Title field should be editable"

        widget.context_length_field.setValue(2048)
        assert widget.context_length_field.value() == 2048, "Context length field should be editable"

        widget.max_tokens_field.setValue(256)
        assert widget.max_tokens_field.value() == 256, "Max tokens field should be editable"

    def test_archived_checkbox_moved_from_completions(self, qt_app, app_with_dataset, ensure_google_icon_font):
        """
        Test that the show archived checkbox is moved from completions panel to controls panel.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        app = app_with_dataset
        widget = WidgetSample(None, app, None)
        widget.show()
        qt_app.processEvents()

        # Check that show_archived_checkbox is not in the completion controls layout
        completion_controls_widgets = []
        if hasattr(widget, 'completion_controls_layout'):
            for i in range(widget.completion_controls_layout.count()):
                item = widget.completion_controls_layout.itemAt(i)
                if item and item.widget():
                    completion_controls_widgets.append(item.widget())

        # The checkbox should not be in the completion controls layout anymore
        assert widget.show_archived_checkbox not in completion_controls_widgets, \
            "Show archived checkbox should be moved from completion controls to main controls"
