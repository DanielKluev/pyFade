"""
Completions filtering logic for WidgetSample.

This module provides a unified API for filtering completions based on various criteria
including model, rating, truncation status, and archive status.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.facet import Facet


class CompletionsFilter:
    """
    Manages filtering of completions based on multiple criteria.

    Filters work together with AND logic - a completion must match all active filters to be displayed.
    Filter state can be persisted and restored via configuration dictionaries.
    """

    def __init__(self):
        """
        Initialize filter with all filters inactive (show everything).
        """
        self.log = logging.getLogger("CompletionsFilter")

        # Filter states (True = filter is active and will hide matching items)
        self.hide_other_models = False  # Hide completions with different exact model_id
        self.hide_other_families = False  # Hide completions from different model families
        self.hide_rated = False  # Hide completions with any rating
        self.hide_low_rated = False  # Hide completions with rating < 3
        self.hide_unrated = False  # Hide completions without rating
        self.hide_full = False  # Hide non-truncated completions
        self.hide_truncated = False  # Hide truncated completions
        self.hide_archived = True  # Hide archived completions (default active)

        # Target model for filtering (exact match and family match)
        self.target_model_id: str | None = None

    def set_target_model_id(self, model_id: str | None):
        """
        Set the target model ID for model-based filtering.

        Args:
            model_id: Model ID to use as reference for filtering, or None to disable model filtering
        """
        self.target_model_id = model_id
        self.log.debug("Target model ID set to: %s", model_id)

    def set_filter(self, filter_name: str, active: bool):
        """
        Set the state of a specific filter.

        Args:
            filter_name: Name of the filter to set (e.g., 'hide_other_models')
            active: Whether the filter should be active (True = hide matching items)
        """
        if hasattr(self, filter_name):
            setattr(self, filter_name, active)
            self.log.debug("Filter '%s' set to: %s", filter_name, active)
        else:
            self.log.warning("Unknown filter name: %s", filter_name)

    def get_filter(self, filter_name: str) -> bool:
        """
        Get the state of a specific filter.

        Args:
            filter_name: Name of the filter to get

        Returns:
            True if filter is active, False otherwise
        """
        return getattr(self, filter_name, False)

    def to_dict(self) -> dict:
        """
        Export filter state as a dictionary for persistence.

        Returns:
            Dictionary containing all filter states
        """
        return {
            'hide_other_models': self.hide_other_models,
            'hide_other_families': self.hide_other_families,
            'hide_rated': self.hide_rated,
            'hide_low_rated': self.hide_low_rated,
            'hide_unrated': self.hide_unrated,
            'hide_full': self.hide_full,
            'hide_truncated': self.hide_truncated,
            'hide_archived': self.hide_archived,
        }

    def from_dict(self, filter_state: dict):
        """
        Import filter state from a dictionary.

        Args:
            filter_state: Dictionary containing filter states
        """
        for key, value in filter_state.items():
            if hasattr(self, key) and isinstance(value, bool):
                setattr(self, key, value)
        self.log.debug("Filter state loaded from dictionary")

    def should_show_completion(self, completion: "PromptCompletion", facet: "Facet | None" = None) -> bool:
        """
        Determine if a completion should be shown based on current filter settings.

        All active filters are applied with AND logic - completion must pass all filters to be shown.

        Args:
            completion: The completion to check
            facet: Optional facet for rating-based filtering

        Returns:
            True if completion should be shown, False if it should be hidden
        """
        # pylint: disable=too-many-return-statements
        # Archive filter
        if self.hide_archived and completion.is_archived:
            return False

        # Model exact match filter
        if self.hide_other_models and self.target_model_id:
            if completion.model_id != self.target_model_id:
                return False

        # Model family filter
        if self.hide_other_families and self.target_model_id:
            target_family = self._extract_model_family(self.target_model_id)
            completion_family = self._extract_model_family(completion.model_id)
            if target_family != completion_family:
                return False

        # Truncation filters
        if self.hide_truncated and completion.is_truncated:
            return False
        if self.hide_full and not completion.is_truncated:
            return False

        # Rating filters (require facet)
        if facet:
            rating = completion.rating_for_facet(facet)
            rating_value = rating.rating if rating else None

            if self.hide_rated and rating_value is not None:
                return False
            if self.hide_unrated and rating_value is None:
                return False
            if self.hide_low_rated and rating_value is not None and rating_value < 3:
                return False

        return True

    def filter_completions(self, completions: list["PromptCompletion"], facet: "Facet | None" = None) -> list["PromptCompletion"]:
        """
        Filter a list of completions based on current filter settings.

        Args:
            completions: List of completions to filter
            facet: Optional facet for rating-based filtering

        Returns:
            List of completions that pass all active filters
        """
        return [c for c in completions if self.should_show_completion(c, facet)]

    @staticmethod
    def _extract_model_family(model_id: str) -> str:
        """
        Extract the model family from a model ID.

        Examples:
            - "gemma3:12b-it-q4_K_M" -> "gemma3"
            - "llama3:8b" -> "llama3"
            - "qwen2.5:14b" -> "qwen2.5"

        Args:
            model_id: Full model identifier

        Returns:
            Model family name (part before colon, or full ID if no colon)
        """
        if ":" in model_id:
            return model_id.split(":", 1)[0]
        return model_id
