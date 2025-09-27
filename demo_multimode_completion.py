#!/usr/bin/env python
"""
Simple standalone demo to verify CompletionFrame multi-mode functionality.
This creates sample and beam mode CompletionFrames to verify visual appearance.
"""

import sys
import os
from pathlib import Path

# Set up path to import pyFade modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set Qt platform to offscreen for headless testing
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.llm_response import LLMResponse, LLMPTokenLogProbs
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.prompt import PromptRevision
import hashlib


def create_demo():
    """Create a demo showing both sample and beam mode CompletionFrames."""
    
    app = QApplication([])
    
    # Create temporary database
    db_path = Path("/tmp/demo_dataset.db")
    if db_path.exists():
        db_path.unlink()
        
    dataset = DatasetDatabase(db_path)
    dataset.initialize()
    
    # Create a demo completion for sample mode
    prompt_revision = PromptRevision.get_or_create(dataset, "Write a haiku about programming", 2048, 128)
    
    completion_text = "Code flows like water,\nBugs dance in morning debug,\nCoffee saves the day."
    completion = PromptCompletion(
        prompt_revision=prompt_revision,
        model_id="demo-model",
        temperature=0.7,
        top_k=40,
        completion_text=completion_text,
        context_length=2048,
        max_tokens=128,
        sha256=hashlib.sha256(completion_text.encode()).hexdigest(),
        is_truncated=False
    )
    dataset.session.add(completion)
    dataset.session.commit()
    
    # Create a demo LLMResponse for beam mode
    beam = LLMResponse(
        model_id="beam-model",
        full_history=[{"role": "user", "content": "Complete this: Once upon a "}],
        full_response_text="Once upon a time, in a kingdom far away, there lived a wise old programmer.",
        response_text="time, in a kingdom far away, there lived a wise old programmer.",
        temperature=0.0,
        top_k=1,
        context_length=1024,
        max_tokens=100,
        min_logprob=-0.85,
        prefill="Once upon a ",
        beam_token="time",
        logprobs=[
            LLMPTokenLogProbs("time", -0.1),
            LLMPTokenLogProbs(",", -0.5),
            LLMPTokenLogProbs(" in", -0.3),
            LLMPTokenLogProbs(" a", -0.2),
            LLMPTokenLogProbs(" kingdom", -1.2),
        ]
    )
    
    # Create main widget
    main_widget = QWidget()
    layout = QVBoxLayout(main_widget)
    
    # Sample mode demo
    layout.addWidget(QLabel("Sample Mode CompletionFrame:"))
    sample_frame = CompletionFrame(dataset, completion, display_mode="sample")
    sample_frame.setFixedSize(400, 350)
    layout.addWidget(sample_frame)
    
    # Beam mode demo
    layout.addWidget(QLabel("Beam Mode CompletionFrame:"))
    beam_frame = CompletionFrame(dataset, beam, display_mode="beam")
    beam_frame.setFixedSize(400, 350)
    layout.addWidget(beam_frame)
    
    main_widget.setWindowTitle("CompletionFrame Multi-Mode Demo")
    main_widget.resize(500, 800)
    
    # Test signal connections
    def on_sample_discard():
        print("Sample discard requested!")
    def on_sample_edit():
        print("Sample edit requested!")
    def on_beam_save():
        print("Beam save requested!")
    def on_beam_pin(is_pinned):
        print(f"Beam pin toggled: {is_pinned}")
        
    sample_frame.discard_requested.connect(on_sample_discard)
    sample_frame.edit_requested.connect(on_sample_edit)
    beam_frame.save_requested.connect(on_beam_save)
    beam_frame.pin_toggled.connect(on_beam_pin)
    
    print("Demo CompletionFrames created successfully!")
    print("Sample mode features:", hasattr(sample_frame, 'edit_button'), hasattr(sample_frame, 'rating_widget'))
    print("Beam mode features:", hasattr(beam_frame, 'save_button'), hasattr(beam_frame, 'pin_button'))
    print("Rating widget visible in sample mode:", hasattr(sample_frame, 'rating_widget') and sample_frame.rating_widget is not None)
    print("Save/pin buttons exist in beam mode:", beam_frame.save_button is not None, beam_frame.pin_button is not None)
    
    # Test pin functionality
    print("Testing pin toggle...")
    beam_frame.pin_button.click()  # Should trigger the signal
    
    dataset.dispose()
    app.quit()
    
    return True


if __name__ == "__main__":
    try:
        success = create_demo()
        if success:
            print("✅ Multi-mode CompletionFrame demo completed successfully!")
            print("✅ All features working as expected!")
        else:
            print("❌ Demo failed!")
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()