"""
Base wizard class to eliminate code duplication between import and export wizards.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QWidget,
    QTextEdit,
    QProgressBar,
)

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class BaseWizard(QDialog):
    """
    Base class for step-by-step wizard dialogs.
    
    Provides common UI components and navigation functionality.
    Subclasses should override abstract methods to implement specific wizard steps.
    """

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase", title: str):
        super().__init__(parent)

        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.dataset = dataset

        # UI components (will be initialized in setup_ui)
        self.content_stack: QStackedWidget | None = None
        self.back_button: QPushButton | None = None
        self.next_button: QPushButton | None = None
        self.cancel_button: QPushButton | None = None

        # Set up the wizard
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(800, 600)

        self.setup_ui()
        self.setup_step_widgets()
        self.show_step(0)

    def setup_ui(self):  # pylint: disable=duplicate-code
        """
        Create and arrange the common wizard UI components.
        """
        main_layout = QVBoxLayout(self)

        # Header
        header_label = QLabel(self.windowTitle(), self)
        header_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(header_label)

        # Step content area
        self.content_stack = QStackedWidget(self)
        main_layout.addWidget(self.content_stack)

        # Navigation buttons
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("← Back", self)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)

        self.next_button = QPushButton("Next →", self)
        self.next_button.clicked.connect(self.go_next)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.next_button)

        main_layout.addLayout(button_layout)

    def setup_step_widgets(self):
        """
        Create and add step widgets to the wizard.
        
        Subclasses must override this method to create their specific step widgets.
        """
        raise NotImplementedError("Subclasses must implement setup_step_widgets")

    def show_step(self, step: int):
        """
        Show the specified step and update navigation buttons.
        
        Subclasses can override this to implement custom step-specific behavior.
        """
        if not self.content_stack:
            return

        self.content_stack.setCurrentIndex(step)

        # Update navigation buttons
        self.back_button.setEnabled(step > 0)
        self.update_next_button()

    def update_next_button(self):
        """
        Update the Next button state based on current step validation.
        
        Subclasses should override this to implement step-specific validation.
        """
        if self.next_button:
            self.next_button.setEnabled(True)

    def go_next(self):
        """
        Advance to the next step.
        
        Subclasses can override this to implement custom navigation logic.
        """
        if not self.content_stack:
            return

        current_step = self.content_stack.currentIndex()
        max_steps = self.content_stack.count() - 1

        if current_step < max_steps:
            self.show_step(current_step + 1)

    def go_back(self):
        """
        Go back to the previous step.
        """
        if not self.content_stack:
            return

        current_step = self.content_stack.currentIndex()
        if current_step > 0:
            self.show_step(current_step - 1)

    def create_progress_widget(self, info_text: str = "Operation in progress. Please wait...",
                               initial_status: str = "Ready to start...") -> QWidget:
        """
        Create a standard progress widget with progress bar and status label.
        
        Args:
            info_text: Text to show above the progress bar
            initial_status: Initial text for the status label
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Progress information
        info_label = QLabel(info_text, widget)
        info_label.setStyleSheet("font-size: 14px; margin-bottom: 20px;")
        layout.addWidget(info_label)

        # Progress bar
        progress_bar = QProgressBar(widget)
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setObjectName("progress_bar")  # For easy access by subclasses
        layout.addWidget(progress_bar)

        # Status label
        progress_label = QLabel(initial_status, widget)
        progress_label.setObjectName("progress_label")  # For easy access by subclasses
        layout.addWidget(progress_label)

        layout.addStretch()
        return widget

    def create_results_widget(self, summary_text: str = "Operation completed!") -> QWidget:
        """
        Create a standard results widget with text area for displaying results.
        
        Args:
            summary_text: Text to show in the summary label
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Results summary
        results_label = QLabel(summary_text, widget)
        results_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        results_label.setObjectName("results_label")  # For easy access by subclasses
        layout.addWidget(results_label)

        # Results details
        results_text = QTextEdit(widget)
        results_text.setReadOnly(True)
        results_text.setObjectName("results_text")  # For easy access by subclasses
        layout.addWidget(results_text)

        return widget
