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