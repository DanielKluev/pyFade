#!/usr/bin/env python3
"""Demonstration script for enhanced CompletionFrame with multi-mode support."""

import sys
import os
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt

# Add the project path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.providers.llm_response import LLMResponse


class CompletionFrameDemo(QMainWindow):
    """Demo window showing both sample and beam modes side by side."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced CompletionFrame Demo - Sample vs Beam Mode")
        self.setGeometry(100, 100, 1000, 600)
        
        # Load Google icon font
        google_icon_font.load()
        
        # Create mock objects
        self.mock_dataset = Mock()
        self.mock_completion = self._create_mock_completion()
        self.mock_beam = self._create_mock_beam()
        
        # Set up UI
        self.setup_ui()
        
        # Connect signals for demo
        self.connect_demo_signals()
        
    def _create_mock_completion(self):
        """Create a mock PromptCompletion for sample mode."""
        completion = Mock()
        completion.id = 1
        completion.model_id = "llama3-8b"
        completion.temperature = 0.7
        completion.top_k = 40
        completion.completion_text = ("Once upon a time in a magical kingdom, there lived a wise old wizard "
                                    "who possessed the most extraordinary collection of enchanted books...")
        completion.is_archived = False
        completion.is_truncated = True  # To show resume button
        completion.prefill = "Once upon"
        completion.beam_token = None
        completion.logprobs = []
        return completion
    
    def _create_mock_beam(self):
        """Create a mock LLMResponse for beam mode."""
        beam = Mock(spec=LLMResponse)
        beam.model_id = "llama3-8b"
        beam.full_response_text = ("In the depths of the enchanted forest, mystical creatures gathered around "
                                 "ancient oak trees, sharing tales of adventure and wonder...")
        beam.min_logprob = -0.234
        return beam
        
    def setup_ui(self):
        """Set up the demo UI with both frame types."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        
        # Sample mode frame
        sample_label = QLabel("<b>Sample Mode (Traditional)</b>")
        sample_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sample_label.setFixedHeight(30)
        
        self.sample_frame = CompletionFrame(
            dataset=self.mock_dataset,
            completion=self.mock_completion,
            display_mode="sample"
        )
        self.sample_frame.setFixedWidth(480)
        self.sample_frame.setFixedHeight(500)
        
        # Beam mode frame
        beam_label = QLabel("<b>Beam Mode (New)</b>")
        beam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beam_label.setFixedHeight(30)
        
        self.beam_frame = CompletionFrame(
            dataset=self.mock_dataset,
            beam=self.mock_beam,
            display_mode="beam"
        )
        self.beam_frame.setFixedWidth(480) 
        self.beam_frame.setFixedHeight(500)
        
        # Layout the frames
        from PyQt6.QtWidgets import QVBoxLayout
        
        sample_container = QWidget()
        sample_layout = QVBoxLayout(sample_container)
        sample_layout.addWidget(sample_label)
        sample_layout.addWidget(self.sample_frame)
        
        beam_container = QWidget()
        beam_layout = QVBoxLayout(beam_container)
        beam_layout.addWidget(beam_label)
        beam_layout.addWidget(self.beam_frame)
        
        layout.addWidget(sample_container)
        layout.addWidget(beam_container)
        
    def connect_demo_signals(self):
        """Connect signals for demo purposes."""
        # Sample mode signals
        self.sample_frame.discarded.connect(lambda c: print(f"Sample discarded: {c.id}"))
        self.sample_frame.edit_requested.connect(lambda c: print(f"Edit requested for: {c.id}"))
        self.sample_frame.resume_requested.connect(lambda c: print(f"Resume requested for: {c.id}"))
        self.sample_frame.archive_toggled.connect(lambda c, state: print(f"Archive toggled: {c.id} -> {state}"))
        
        # Beam mode signals  
        self.beam_frame.discarded.connect(lambda f: print(f"Beam discarded from frame: {id(f)}"))
        self.beam_frame.saved.connect(lambda f, c: print(f"Beam saved from frame: {id(f)}"))
        self.beam_frame.pinned.connect(lambda f, state: print(f"Beam pinned: {id(f)} -> {state}"))


def main():
    """Run the CompletionFrame demo."""
    app = QApplication(sys.argv)
    
    demo = CompletionFrameDemo()
    demo.show()
    
    # Take a screenshot for documentation
    app.processEvents()  # Ensure window is fully rendered
    
    # Capture screenshot
    screen = app.primaryScreen()
    screenshot = screen.grabWindow(demo.winId())
    screenshot.save("/tmp/completion_frame_demo.png")
    print("Screenshot saved to /tmp/completion_frame_demo.png")
    
    # Show for a brief moment then exit (for automated testing)
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(2000, app.quit)  # Exit after 2 seconds
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())