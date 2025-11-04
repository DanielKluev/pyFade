"""
Filter rule classes for complex sample filtering.

Provides data classes and evaluation logic for individual filter rules that can be
combined to create complex sample filters. Supports string search, tag, and facet filters
with optional negation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample
    from py_fade.dataset.tag import Tag
    from py_fade.dataset.facet import Facet


class FilterRuleType(Enum):
    """
    Types of filter rules that can be applied to samples.
    """

    STRING = "string"  # Text search in sample title, group_path, or prompt
    TAG = "tag"  # Filter by tag presence
    FACET = "facet"  # Filter by facet (samples with ratings for this facet)


@dataclass
class FilterRule:
    """
    Represents a single filter rule that can be evaluated against a sample.

    A rule has a type (string, tag, or facet), a value (the search term, tag ID, or facet ID),
    and an optional negation flag to reverse the match result.
    """

    rule_type: FilterRuleType
    value: str | int  # String for text search, int for tag/facet IDs
    negated: bool = False  # If True, the rule matches when the condition is NOT met

    log = logging.getLogger("FilterRule")

    @classmethod
    def from_dict(cls, rule_dict: dict) -> "FilterRule":
        """
        Create a FilterRule from a dictionary representation.

        Args:
            rule_dict: Dictionary with keys 'type', 'value', and optional 'negated'

        Returns:
            A FilterRule instance

        Raises:
            ValueError: If the rule_dict is invalid
        """
        try:
            rule_type_str = rule_dict.get("type", "").lower()
            rule_type = FilterRuleType(rule_type_str)
            value = rule_dict.get("value")
            negated = rule_dict.get("negated", False)

            if value is None:
                raise ValueError("Filter rule must have a 'value' field")

            return cls(rule_type=rule_type, value=value, negated=negated)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid filter rule dictionary: {rule_dict}") from e

    def to_dict(self) -> dict:
        """
        Convert this filter rule to a dictionary representation.

        Returns:
            Dictionary with keys 'type', 'value', and 'negated'
        """
        return {"type": self.rule_type.value, "value": self.value, "negated": self.negated}

    def evaluate(self, sample: "Sample", dataset: "DatasetDatabase") -> bool:
        """
        Evaluate this rule against a sample.

        Args:
            sample: The sample to evaluate against
            dataset: The dataset database instance

        Returns:
            True if the sample matches this rule (considering negation), False otherwise
        """
        if self.rule_type == FilterRuleType.STRING:
            result = self._evaluate_string(sample)
        elif self.rule_type == FilterRuleType.TAG:
            result = self._evaluate_tag(sample, dataset)
        elif self.rule_type == FilterRuleType.FACET:
            result = self._evaluate_facet(sample, dataset)
        else:
            self.log.warning("Unknown filter rule type: %s", self.rule_type)
            result = False

        # Apply negation if needed
        return not result if self.negated else result

    def _evaluate_string(self, sample: "Sample") -> bool:
        """
        Evaluate a string search rule.

        Searches in sample title, group_path, and prompt text.

        Args:
            sample: The sample to evaluate against

        Returns:
            True if the search string is found, False otherwise
        """
        if not isinstance(self.value, str):
            return False

        search_term = self.value.lower().strip()
        if not search_term:
            return True  # Empty search matches everything

        # Search in title
        if search_term in sample.title.lower():
            return True

        # Search in group_path
        if sample.group_path and search_term in sample.group_path.lower():
            return True

        # Search in prompt text
        if sample.prompt_revision and search_term in sample.prompt_revision.prompt_text.lower():
            return True

        return False

    def _evaluate_tag(self, sample: "Sample", dataset: "DatasetDatabase") -> bool:
        """
        Evaluate a tag filter rule.

        Checks if the sample has the specified tag.

        Args:
            sample: The sample to evaluate against
            dataset: The dataset database instance

        Returns:
            True if the sample has the tag, False otherwise
        """
        if not isinstance(self.value, int):
            return False

        tag_id = self.value

        # Get fresh tags from the database
        sample_tags = sample.get_tags(dataset)
        return any(tag.id == tag_id for tag in sample_tags)

    def _evaluate_facet(self, sample: "Sample", dataset: "DatasetDatabase") -> bool:  # pylint: disable=unused-argument
        """
        Evaluate a facet filter rule.

        Checks if the sample has any completions with ratings for the specified facet.

        Args:
            sample: The sample to evaluate against
            dataset: The dataset database instance

        Returns:
            True if the sample has ratings for this facet, False otherwise
        """
        if not isinstance(self.value, int):
            return False

        facet_id = self.value

        # Check if any completion for this sample has a rating for this facet
        if not sample.prompt_revision:
            return False

        for completion in sample.prompt_revision.completions:
            for rating in completion.ratings:
                if rating.facet_id == facet_id:
                    return True

        return False

    def get_display_text(self, dataset: "DatasetDatabase") -> str:
        """
        Get a human-readable description of this filter rule.

        Args:
            dataset: The dataset database instance for looking up tag/facet names

        Returns:
            A human-readable string describing this rule
        """
        prefix = "NOT " if self.negated else ""

        if self.rule_type == FilterRuleType.STRING:
            return f'{prefix}Text contains "{self.value}"'
        if self.rule_type == FilterRuleType.TAG:
            from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel
            if self.value is not None:
                tag = Tag.get_by_id(dataset, int(self.value))
                tag_name = tag.name if tag else f"Tag #{self.value}"
            else:
                tag_name = "Tag #(unknown)"
            return f'{prefix}Tag "{tag_name}"'
        if self.rule_type == FilterRuleType.FACET:
            from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel
            if self.value is not None:
                facet = Facet.get_by_id(dataset, int(self.value))
                facet_name = facet.name if facet else f"Facet #{self.value}"
            else:
                facet_name = "Facet #(unknown)"
            return f'{prefix}Facet "{facet_name}"'

        return f"{prefix}Unknown rule type"
