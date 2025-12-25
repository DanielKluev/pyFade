"""Token picker widget used to inspect and select probable next tokens."""

import logging
import unicodedata

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.auxillary.aux_logprobs_to_color import logprob_to_qcolor
from py_fade.gui.components.widget_toggle_button import QPushButtonToggle
from py_fade.data_formats.base_data_classes import SinglePositionToken, SinglePositionTopLogprobs

SYMBOLS_MAP = {
    " ": "␣",
    "\n": "⏎",
    "\t": "→",
}


class WidgetTokenPicker(QWidget):
    """
    Component widget for picking tokens.
    Sorts by logprob, coloring by logprob value via `logprob_to_qcolor`.

    Can either be single-select (button-like) or multi-select (checkbox-like).

    If multi-select, at the bottom is a button to accept the selection. For single-select, selection is immediate.
    Emits `tokens_selected` signal with list of selected tokens when selection is finalized.

    Displays tokens with their logprobs, amount per row depending on width of the widget, filling without wrapping or horizontal scroll.

    Includes filtering capabilities:
    - Text search: filters tokens containing the search string
    - Latin-only filter: shows only tokens with Latin letters and punctuation (including line breaks)
    - Space-prefix filter: shows only tokens starting with a space
    - No-space-prefix filter: shows only tokens NOT starting with a space
    Filters can be combined and are applied via AND logic.
    """

    tokens_selected = pyqtSignal(list)  # Signal emitted with list of selected tokens
    tokens: SinglePositionTopLogprobs  # List of (token, logprob) tuples
    tokens_map: dict[int, SinglePositionToken]  # Token_id -> SinglePositionToken
    multi_select: bool  # Whether multi-select mode is enabled

    # Filter state
    filter_text: str  # Text search filter
    filter_latin_only: bool  # Show only Latin characters
    filter_space_prefix: bool  # Show only tokens with space prefix
    filter_no_space_prefix: bool  # Show only tokens without space prefix

    def __init__(self, parent: QWidget | None, tokens: SinglePositionTopLogprobs, multi_select: bool = False):
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.multi_select = multi_select
        self.selected_tokens: set[int] = set()
        self.tokens = tokens
        #self.tokens.sort(key=lambda x: x[1], reverse=True)  # sort by logprob descending
        self.log.info("[ > ] Token picker with tokens:\n\t%s", self.tokens)
        self.tokens_map = {t.token_id: t for t in self.tokens}

        self.token_widgets: list[QWidget] = []  # Keep references to token widgets

        # Initialize filter state
        self.filter_text = ""
        self.filter_latin_only = False
        self.filter_space_prefix = False
        self.filter_no_space_prefix = False

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create filter controls section
        filter_layout = QVBoxLayout()

        # Text search filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter tokens by text...")
        self.search_input.textChanged.connect(self._on_filter_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        filter_layout.addLayout(search_layout)

        # Toggle button filters
        toggle_layout = QHBoxLayout()
        toggle_layout.addWidget(QLabel("Filters:"))

        self.latin_only_button = QPushButtonToggle("abc", "Latin letters and punctuation only", icon_size=20, button_size=32)
        self.latin_only_button.toggled_state_changed.connect(self._on_latin_only_toggled)
        toggle_layout.addWidget(self.latin_only_button)

        self.space_prefix_button = QPushButtonToggle("space_bar", "Only tokens with space prefix", icon_size=20, button_size=32)
        self.space_prefix_button.toggled_state_changed.connect(self._on_space_prefix_toggled)
        toggle_layout.addWidget(self.space_prefix_button)

        self.no_space_prefix_button = QPushButtonToggle("text_fields", "Only tokens without space prefix", icon_size=20, button_size=32)
        self.no_space_prefix_button.toggled_state_changed.connect(self._on_no_space_prefix_toggled)
        toggle_layout.addWidget(self.no_space_prefix_button)

        toggle_layout.addStretch()
        filter_layout.addLayout(toggle_layout)

        main_layout.addLayout(filter_layout)

        # Create scroll area for tokens
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create widget to contain the grid
        tokens_widget = QWidget()
        self.tokens_grid = QGridLayout()
        self.tokens_grid.setContentsMargins(5, 5, 5, 5)
        self.tokens_grid.setSpacing(3)
        tokens_widget.setLayout(self.tokens_grid)

        scroll_area.setWidget(tokens_widget)
        main_layout.addWidget(scroll_area)

        # Populate tokens
        self._populate_tokens()

        # Add accept button for multi-select mode
        if self.multi_select:
            self.accept_button = QPushButton("Accept Selection")
            self.accept_button.clicked.connect(self._emit_selection)
            main_layout.addWidget(self.accept_button)

    def _on_filter_changed(self, text: str):
        """Handle text search filter change."""
        self.filter_text = text.lower()
        self._refresh_tokens()

    def _on_latin_only_toggled(self, state: bool):
        """Handle Latin-only filter toggle."""
        self.filter_latin_only = state
        self._refresh_tokens()

    def _on_space_prefix_toggled(self, state: bool):
        """Handle space-prefix filter toggle."""
        self.filter_space_prefix = state
        self._refresh_tokens()

    def _on_no_space_prefix_toggled(self, state: bool):
        """Handle no-space-prefix filter toggle."""
        self.filter_no_space_prefix = state
        self._refresh_tokens()

    def _token_passes_filters(self, token: SinglePositionToken) -> bool:
        """
        Check if a token passes all active filters.

        Filters are combined via AND logic - token must pass all active filters to be shown.

        Returns True if token should be displayed, False otherwise.
        """
        # Text search filter
        if self.filter_text and self.filter_text not in token.token_str.lower():
            return False

        # Latin-only filter: check if all characters are Latin, punctuation, or whitespace
        if self.filter_latin_only:
            if not self._is_latin_or_punctuation(token.token_str):
                return False

        # Space prefix filter (mutually exclusive with no-space prefix)
        if self.filter_space_prefix and not token.token_str.startswith(" "):
            return False

        if self.filter_no_space_prefix and token.token_str.startswith(" "):
            return False

        return True

    def _is_latin_or_punctuation(self, text: str) -> bool:
        """
        Check if text contains only Latin letters, punctuation, or whitespace.

        This filters out non-Latin scripts like Arabic, CJK, Cyrillic, etc.
        """
        for char in text:
            # Allow whitespace characters (space, newline, tab, etc.)
            if char.isspace():
                continue

            # Get Unicode category
            category = unicodedata.category(char)

            # Allow punctuation (all P* categories)
            if category.startswith('P'):
                continue

            # For letters and marks, check if they're Latin
            if category.startswith('L') or category.startswith('M'):
                # Check if character is in Latin script ranges
                # Basic Latin: U+0000-U+007F
                # Latin-1 Supplement: U+0080-U+00FF
                # Latin Extended-A: U+0100-U+017F
                # Latin Extended-B: U+0180-U+024F
                # Latin Extended Additional: U+1E00-U+1EFF
                char_code = ord(char)
                is_latin = ((0x0000 <= char_code <= 0x007F) or (0x0080 <= char_code <= 0x00FF) or (0x0100 <= char_code <= 0x017F) or
                            (0x0180 <= char_code <= 0x024F) or (0x1E00 <= char_code <= 0x1EFF))
                if not is_latin:
                    return False
            # Allow digits and symbols
            elif category.startswith('N') or category.startswith('S'):
                continue
            # Reject other categories (like control characters, format chars, etc.)
            else:
                return False

        return True

    def _refresh_tokens(self):
        """Refresh the token display by clearing and repopulating with current filters."""
        # Clear existing widgets
        for widget in self.token_widgets:
            widget.deleteLater()
        self.token_widgets.clear()

        # Clear the grid layout
        while self.tokens_grid.count():
            item = self.tokens_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Repopulate with filtered tokens
        self._populate_tokens()

    def _populate_tokens(self):
        """Populate the grid with token widgets, applying active filters."""
        if not self.tokens:
            return

        # Calculate optimal number of columns based on widget width
        # We'll start with a reasonable default and let Qt handle the layout
        columns_per_row = 6  # Default, can be adjusted based on widget width

        row = 0
        col = 0

        for token in self.tokens:
            # Skip tokens that don't pass filters
            if not self._token_passes_filters(token):
                continue

            if self.multi_select:
                widget = self._create_checkbox_token(token)
            else:
                widget = self._create_button_token(token)

            self.token_widgets.append(widget)
            self.tokens_grid.addWidget(widget, row, col)

            col += 1
            if col >= columns_per_row:
                col = 0
                row += 1

    def _sanitize_token_display(self, token_str: str) -> str:
        """Sanitize token for display, replacing special characters."""
        for symbol, replacement in SYMBOLS_MAP.items():
            token_str = token_str.replace(symbol, replacement)
        return token_str

    def _create_button_token(self, token: SinglePositionToken) -> QPushButton:
        """Create a button widget for single-select mode."""
        token_str = self._sanitize_token_display(token.token_str)
        button = QPushButton(f"{token_str} [{token.logprob:.2f}]")
        button.setCheckable(True)

        # Set color based on logprob
        color = logprob_to_qcolor(token.logprob)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color.name()};
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px;
                margin: 1px;
                min-width: 80px;
                min-height: 40px;
                color: black;
                font-weight: bold;
                text-transform: none;
            }}
            QPushButton:checked {{
                border: 3px solid #000;
                background-color: {color.darker(150).name()};
            }}
            QPushButton:hover {{
                border: 2px solid #666;
            }}
        """)

        button.clicked.connect(lambda checked, t=token: self._on_single_select(t, checked))

        # Restore checked state if this token was previously selected
        if token.token_id in self.selected_tokens:
            button.setChecked(True)

        return button

    def _create_checkbox_token(self, token: SinglePositionToken) -> QWidget:
        """Create a checkbox widget for multi-select mode."""
        token_str = self._sanitize_token_display(token.token_str)
        checkbox = QCheckBox(f"{token_str} [{token.logprob:.2f}]")

        # Set color based on logprob
        color = logprob_to_qcolor(token.logprob)
        checkbox.setStyleSheet(f"""
            QCheckBox {{
                background-color: {color.name()};
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px;
                margin: 1px;
                min-width: 80px;
                min-height: 40px;
                color: black;
                font-weight: bold;
            }}
            QCheckBox:checked {{
                background-color: {color.darker(150).name()};
                border: 3px solid #000;
            }}
            QCheckBox:hover {{
                border: 2px solid #666;
            }}
        """)

        checkbox.stateChanged.connect(lambda state, t=token: self._on_multi_select(t, state == Qt.CheckState.Checked.value))

        # Restore checked state if this token was previously selected
        if token.token_id in self.selected_tokens:
            checkbox.setChecked(True)

        return checkbox

    def _on_single_select(self, token: SinglePositionToken, checked: bool):
        """Handle single-select token selection."""
        if checked:
            # Uncheck all other buttons
            for widget in self.token_widgets:
                if isinstance(widget, QPushButton):
                    # Compare widget text with the token's display text
                    # Extract just the token string part (before the logprob display)
                    widget_token_str = widget.text().split(" [")[0]
                    # Get the token's sanitized display string for comparison
                    token_display_str = self._sanitize_token_display(token.token_str)
                    if widget_token_str != token_display_str:
                        widget.setChecked(False)

            self.selected_tokens.clear()
            self.selected_tokens.add(token.token_id)
            # Emit immediately for single-select
            self._emit_selection()
        else:
            self.selected_tokens.discard(token.token_id)

    def _on_multi_select(self, token: SinglePositionToken, checked: bool):
        """Handle multi-select token selection."""
        if checked:
            self.selected_tokens.add(token.token_id)
        else:
            self.selected_tokens.discard(token.token_id)

    def _emit_selection(self):
        """Emit the tokens_selected signal with current selection."""
        selected_list = self.get_selected_tokens()
        self.log.info("Emitting selected tokens: %s", selected_list)
        self.tokens_selected.emit(selected_list)

    def get_selected_tokens(self) -> list[SinglePositionToken]:
        """Get the currently selected tokens."""
        result = []
        for token_id in self.selected_tokens:
            if token_id in self.tokens_map:
                result.append(self.tokens_map[token_id])
        return result

    def clear_selection(self):
        """Clear the current selection."""
        self.selected_tokens.clear()

        # Uncheck all widgets
        for widget in self.token_widgets:
            if isinstance(widget, QPushButton):
                widget.setChecked(False)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
