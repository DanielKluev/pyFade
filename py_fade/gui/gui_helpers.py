"""Common imports, types, and utilities for GUI components."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


def get_dataset_preferences(app: "pyFadeApp", dataset_key: str) -> dict:
    """
    Get preferences for a specific dataset.

    Returns a validated dictionary of dataset preferences for the given key.
    If preferences don't exist or are invalid, returns an empty dictionary.

    Args:
        app: Application instance with config
        dataset_key: Key identifying the dataset (typically resolved db_path)

    Returns:
        Dictionary of dataset preferences
    """
    if not hasattr(app, "config"):
        return {}
    preferences = getattr(app.config, "dataset_preferences", {})
    if not isinstance(preferences, dict):
        return {}
    dataset_prefs = preferences.get(dataset_key, {})
    if not isinstance(dataset_prefs, dict):
        return {}
    return dataset_prefs


def update_dataset_preferences(app: "pyFadeApp", dataset_key: str, updates: dict) -> None:
    """
    Update and persist preferences for a specific dataset.

    Safely merges the provided updates into the dataset preferences and saves the configuration.

    Args:
        app: Application instance with config
        dataset_key: Key identifying the dataset (typically resolved db_path)
        updates: Dictionary of preference updates to apply
    """
    if not hasattr(app, "config"):
        return
    preferences = getattr(app.config, "dataset_preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
    dataset_prefs = preferences.get(dataset_key, {})
    if not isinstance(dataset_prefs, dict):
        dataset_prefs = {}

    # Apply updates
    dataset_prefs.update(updates)

    # Save back
    preferences[dataset_key] = dataset_prefs
    app.config.dataset_preferences = preferences
    app.config.save()
