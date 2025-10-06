"""Token picker widget used to inspect and select probable next tokens."""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.auxillary.aux_logprobs_to_color import logprob_to_qcolor
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
    """

    tokens_selected = pyqtSignal(list)  # Signal emitted with list of selected tokens
    tokens: SinglePositionTopLogprobs  # List of (token, logprob) tuples
    tokens_map: dict[int, SinglePositionToken]  # Token_id -> SinglePositionToken
    multi_select: bool  # Whether multi-select mode is enabled

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

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

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

    def _populate_tokens(self):
        """Populate the grid with token widgets."""
        if not self.tokens:
            return

        # Calculate optimal number of columns based on widget width
        # We'll start with a reasonable default and let Qt handle the layout
        columns_per_row = 6  # Default, can be adjusted based on widget width

        row = 0
        col = 0

        for token in self.tokens:
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
        return checkbox

    def _on_single_select(self, token: SinglePositionToken, checked: bool):
        """Handle single-select token selection."""
        if checked:
            # Uncheck all other buttons
            for widget in self.token_widgets:
                if isinstance(widget, QPushButton):
                    # Get the token from the widget's text (first line before \n)
                    widget_token = widget.text().split("\n")[0]
                    if widget_token != token:
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
