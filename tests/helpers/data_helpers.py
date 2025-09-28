"""
Database and data setup helpers for testing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase

from py_fade.dataset.facet import Facet


def ensure_test_facets(dataset: "DatasetDatabase") -> List[Facet]:
    """
    Create standard test facets in the dataset if they don't exist.
    
    Returns a list of facets that can be used in tests for consistent behavior.
    """
    facet_specs = [
        ("Reasoning", "Logical reasoning and problem-solving capability"),
        ("Creativity", "Creative and imaginative responses"),  
        ("Safety", "Safe and appropriate content generation"),
        ("Accuracy", "Factual accuracy and correctness")
    ]
    
    facets = []
    for name, description in facet_specs:
        facet = Facet.get_by_name(dataset, name)
        if not facet:
            facet = Facet(name=name, description=description)
            dataset.session.add(facet)
            dataset.session.commit()
        facets.append(facet)
    
    return facets


def create_test_app(tmp_path, monkeypatch, qt_app):
    """
    Create a test app instance with temporary home directory.
    
    This is a common pattern used across multiple test files.
    """
    import pathlib
    from py_fade.app import pyFadeApp
    
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

    config_path = fake_home / "config.yaml"
    return pyFadeApp(config_path=config_path)


def create_test_completion(session, prompt_revision, completion_overrides=None):
    """
    Create a test PromptCompletion with common defaults.
    
    This helper eliminates duplicate completion creation code across test files.
    """
    from py_fade.dataset.completion import PromptCompletion
    
    completion_defaults = {
        "prompt_revision": prompt_revision,
        "model_id": "test-model",
        "full_history": [{"role": "user", "content": "Test prompt"}],
        "prefill": "",
        "beam_token": "",
        "completion_text": "Test completion",
        "tags": None,
        "context_length": 2048,
        "max_tokens": 128,
        "is_truncated": False,
        "is_archived": False,
    }
    if completion_overrides:
        completion_defaults.update(completion_overrides)
    
    completion = PromptCompletion(**completion_defaults)
    session.add(completion)
    session.commit()
    
    return completion


def setup_widget_test_environment(temp_dataset, app_with_dataset, qt_app):
    """
    Set up common test environment for widget tests.
    
    This helper eliminates duplicate setup code across widget test files.
    """
    from py_fade.gui.widget_dataset_top import WidgetDatasetTop
    
    session = temp_dataset.session
    assert session is not None
    session.flush()
    session.commit()

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()
    
    return widget