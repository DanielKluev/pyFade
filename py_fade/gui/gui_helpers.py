"""Common imports, types, and utilities for GUI components."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


def shorten_tab_title(title: str) -> str:
    """
    Shorten a tab title if it's longer than 8 words.
    
    If the title has more than 8 words (counting by spaces), keeps the first 6 words
    and the last 2 words, replacing everything in between with "...".
    Titles with 8 or fewer words are returned unchanged.
    
    Args:
        title: The original tab title
        
    Returns:
        The shortened title if it had more than 8 words, otherwise the original title
    """
    if not title:
        return title
    
    # Split by whitespace and filter out empty strings
    words = title.split()
    
    # If 8 words or fewer, return unchanged
    if len(words) <= 8:
        return title
    
    # Keep first 6 and last 2 words, add "..." in between
    first_six = words[:6]
    last_two = words[-2:]
    shortened_words = first_six + ["..."] + last_two
    
    return " ".join(shortened_words)


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
