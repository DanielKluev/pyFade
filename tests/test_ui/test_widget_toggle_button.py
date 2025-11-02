"""
Tests for the QPushButtonToggle widget component.
"""
# pylint: disable=protected-access

from py_fade.gui.components.widget_toggle_button import QPushButtonToggle


def test_toggle_button_initial_state(ensure_google_icon_font, qt_app):
    """Test that toggle button initializes in untoggled state."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    button = QPushButtonToggle("check", "Test toggle")
    qt_app.processEvents()

    assert not button.is_toggled()
    assert button.toolTip() == "Test toggle"


def test_toggle_button_click_changes_state(ensure_google_icon_font, qt_app):
    """Test that clicking the button toggles its state."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    button = QPushButtonToggle("check", "Test toggle")
    qt_app.processEvents()

    # Initial state
    assert not button.is_toggled()

    # Click to toggle on
    button.click()
    qt_app.processEvents()
    assert button.is_toggled()

    # Click again to toggle off
    button.click()
    qt_app.processEvents()
    assert not button.is_toggled()


def test_toggle_button_emits_signal(ensure_google_icon_font, qt_app):
    """Test that toggle button emits signal when state changes."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    button = QPushButtonToggle("check", "Test toggle")
    qt_app.processEvents()

    signals_received = []

    def record_signal(state):
        signals_received.append(state)

    button.toggled_state_changed.connect(record_signal)

    # Toggle on
    button.click()
    qt_app.processEvents()
    assert signals_received == [True]

    # Toggle off
    button.click()
    qt_app.processEvents()
    assert signals_received == [True, False]


def test_toggle_button_set_toggled_programmatically(ensure_google_icon_font, qt_app):
    """Test that toggle state can be set programmatically without emitting signal."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    button = QPushButtonToggle("check", "Test toggle")
    qt_app.processEvents()

    signals_received = []

    def record_signal(state):
        signals_received.append(state)

    button.toggled_state_changed.connect(record_signal)

    # Set state programmatically
    button.set_toggled(True)
    qt_app.processEvents()
    assert button.is_toggled()
    assert len(signals_received) == 0  # No signal emitted

    # Set to same state
    button.set_toggled(True)
    qt_app.processEvents()
    assert button.is_toggled()
    assert len(signals_received) == 0  # Still no signal

    # Set to different state
    button.set_toggled(False)
    qt_app.processEvents()
    assert not button.is_toggled()
    assert len(signals_received) == 0  # Still no signal


def test_toggle_button_style_updates(ensure_google_icon_font, qt_app):
    """Test that button style updates when toggled."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    button = QPushButtonToggle("check", "Test toggle")
    qt_app.processEvents()

    # Get initial stylesheet
    initial_style = button.styleSheet()
    assert "border: 1px solid" in initial_style  # Untoggled state has 1px border

    # Toggle on and check style changed
    button.click()
    qt_app.processEvents()
    toggled_style = button.styleSheet()
    assert "border: 2px solid" in toggled_style  # Toggled state has 2px border
    assert toggled_style != initial_style

    # Toggle off and check style reverted
    button.click()
    qt_app.processEvents()
    assert button.styleSheet() == initial_style
