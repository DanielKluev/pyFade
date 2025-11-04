"""
Tests for FilterRule evaluation and logic.

Tests for filter rule creation, serialization, and evaluation against samples.
"""

import pytest

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.filter_rule import FilterRule, FilterRuleType
from py_fade.dataset.tag import Tag
from tests.helpers.data_helpers import create_test_sample, create_test_completion_with_params


class TestFilterRuleCreation:
    """Test creating filter rules."""

    def test_create_string_rule(self):
        """
        Test creating a string filter rule.
        """
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="test")

        assert rule.rule_type == FilterRuleType.STRING
        assert rule.value == "test"
        assert rule.negated is False

    def test_create_tag_rule(self):
        """
        Test creating a tag filter rule.
        """
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=42)

        assert rule.rule_type == FilterRuleType.TAG
        assert rule.value == 42
        assert rule.negated is False

    def test_create_facet_rule(self):
        """
        Test creating a facet filter rule.
        """
        rule = FilterRule(rule_type=FilterRuleType.FACET, value=17)

        assert rule.rule_type == FilterRuleType.FACET
        assert rule.value == 17
        assert rule.negated is False

    def test_create_negated_rule(self):
        """
        Test creating a negated filter rule.
        """
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=1, negated=True)

        assert rule.negated is True


class TestFilterRuleSerialization:
    """Test filter rule serialization to/from dictionaries."""

    def test_to_dict_string_rule(self):
        """
        Test converting a string rule to dictionary.
        """
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="search")
        rule_dict = rule.to_dict()

        assert rule_dict == {"type": "string", "value": "search", "negated": False}

    def test_to_dict_tag_rule(self):
        """
        Test converting a tag rule to dictionary.
        """
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=5, negated=True)
        rule_dict = rule.to_dict()

        assert rule_dict == {"type": "tag", "value": 5, "negated": True}

    def test_from_dict_string_rule(self):
        """
        Test creating a string rule from dictionary.
        """
        rule_dict = {"type": "string", "value": "test", "negated": False}
        rule = FilterRule.from_dict(rule_dict)

        assert rule.rule_type == FilterRuleType.STRING
        assert rule.value == "test"
        assert rule.negated is False

    def test_from_dict_tag_rule(self):
        """
        Test creating a tag rule from dictionary.
        """
        rule_dict = {"type": "tag", "value": 10, "negated": True}
        rule = FilterRule.from_dict(rule_dict)

        assert rule.rule_type == FilterRuleType.TAG
        assert rule.value == 10
        assert rule.negated is True

    def test_from_dict_facet_rule(self):
        """
        Test creating a facet rule from dictionary.
        """
        rule_dict = {"type": "facet", "value": 3}
        rule = FilterRule.from_dict(rule_dict)

        assert rule.rule_type == FilterRuleType.FACET
        assert rule.value == 3
        assert rule.negated is False

    def test_from_dict_invalid_type(self):
        """
        Test that invalid rule types raise ValueError.
        """
        rule_dict = {"type": "invalid_type", "value": "test"}

        with pytest.raises(ValueError, match="Invalid filter rule"):
            FilterRule.from_dict(rule_dict)

    def test_from_dict_missing_value(self):
        """
        Test that missing value raises ValueError.
        """
        rule_dict = {"type": "string"}

        with pytest.raises(ValueError, match="Invalid filter rule"):
            FilterRule.from_dict(rule_dict)

    def test_roundtrip_serialization(self):
        """
        Test that rules can be serialized and deserialized without loss.
        """
        original = FilterRule(rule_type=FilterRuleType.TAG, value=42, negated=True)
        rule_dict = original.to_dict()
        restored = FilterRule.from_dict(rule_dict)

        assert restored.rule_type == original.rule_type
        assert restored.value == original.value
        assert restored.negated == original.negated


class TestStringRuleEvaluation:
    """Test evaluation of string search rules."""

    def test_string_rule_matches_title(self, temp_dataset):
        """
        Test that string rule matches sample title.
        """
        sample, _ = create_test_sample(temp_dataset, title="Important Sample")
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="Important")

        assert rule.evaluate(sample, temp_dataset) is True

    def test_string_rule_matches_title_case_insensitive(self, temp_dataset):
        """
        Test that string rule matching is case-insensitive.
        """
        sample, _ = create_test_sample(temp_dataset, title="Important Sample")
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="important")

        assert rule.evaluate(sample, temp_dataset) is True

    def test_string_rule_matches_group_path(self, temp_dataset):
        """
        Test that string rule matches group path.
        """
        sample, _ = create_test_sample(temp_dataset)
        sample.group_path = "category/subcategory"
        temp_dataset.commit()

        rule = FilterRule(rule_type=FilterRuleType.STRING, value="category")

        assert rule.evaluate(sample, temp_dataset) is True

    def test_string_rule_matches_prompt(self, temp_dataset):
        """
        Test that string rule matches prompt text.
        """
        sample, prompt = create_test_sample(temp_dataset)
        prompt.prompt_text = "This is a test prompt"
        temp_dataset.commit()

        rule = FilterRule(rule_type=FilterRuleType.STRING, value="test prompt")
        assert rule.evaluate(sample, temp_dataset) is True

    def test_string_rule_no_match(self, temp_dataset):
        """
        Test that string rule returns False when no match.
        """
        sample, _ = create_test_sample(temp_dataset, title="Sample Title")
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="NotPresent")

        assert rule.evaluate(sample, temp_dataset) is False

    def test_string_rule_empty_matches_all(self, temp_dataset):
        """
        Test that empty string rule matches everything.
        """
        sample, _ = create_test_sample(temp_dataset)
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="")

        assert rule.evaluate(sample, temp_dataset) is True


class TestTagRuleEvaluation:
    """Test evaluation of tag filter rules."""

    def test_tag_rule_matches_when_tag_present(self, temp_dataset):
        """
        Test that tag rule matches when sample has the tag.
        """
        tag = Tag.create(temp_dataset, "TestTag", "Description")
        temp_dataset.commit()  # Ensure tag ID is assigned
        sample, _ = create_test_sample(temp_dataset)
        sample.add_tag(temp_dataset, tag)
        temp_dataset.commit()  # Commit the tag association

        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id)
        assert rule.evaluate(sample, temp_dataset) is True

    def test_tag_rule_no_match_when_tag_absent(self, temp_dataset):
        """
        Test that tag rule returns False when sample doesn't have the tag.
        """
        tag = Tag.create(temp_dataset, "TestTag", "Description")
        temp_dataset.commit()  # Ensure tag ID is assigned
        sample, _ = create_test_sample(temp_dataset)

        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id)
        assert rule.evaluate(sample, temp_dataset) is False

    def test_tag_rule_with_multiple_tags(self, temp_dataset):
        """
        Test tag rule when sample has multiple tags.
        """
        tag1 = Tag.create(temp_dataset, "Tag1", "First tag")
        tag2 = Tag.create(temp_dataset, "Tag2", "Second tag")
        temp_dataset.commit()  # Ensure tag IDs are assigned
        sample, _ = create_test_sample(temp_dataset)
        sample.add_tag(temp_dataset, tag1)
        sample.add_tag(temp_dataset, tag2)
        temp_dataset.commit()  # Commit the tag associations

        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag2.id)
        assert rule.evaluate(sample, temp_dataset) is True


class TestFacetRuleEvaluation:
    """Test evaluation of facet filter rules."""

    def test_facet_rule_matches_when_rated(self, temp_dataset):
        """
        Test that facet rule matches when sample has ratings for the facet.
        """
        facet = Facet.create(temp_dataset, "TestFacet", "Description")
        temp_dataset.commit()  # Ensure facet ID is assigned
        sample, prompt = create_test_sample(temp_dataset)
        completion = create_test_completion_with_params(temp_dataset, prompt, completion_text="test")
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 5)

        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet.id)
        assert rule.evaluate(sample, temp_dataset) is True

    def test_facet_rule_no_match_when_not_rated(self, temp_dataset):
        """
        Test that facet rule returns False when sample has no ratings for the facet.
        """
        facet = Facet.create(temp_dataset, "TestFacet", "Description")
        temp_dataset.commit()  # Ensure facet ID is assigned
        sample, _ = create_test_sample(temp_dataset)

        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet.id)
        assert rule.evaluate(sample, temp_dataset) is False

    def test_facet_rule_with_multiple_facets(self, temp_dataset):
        """
        Test facet rule when sample has ratings for multiple facets.
        """
        facet1 = Facet.create(temp_dataset, "Facet1", "First facet")
        facet2 = Facet.create(temp_dataset, "Facet2", "Second facet")
        temp_dataset.commit()  # Ensure facet IDs are assigned
        sample, prompt = create_test_sample(temp_dataset)
        completion = create_test_completion_with_params(temp_dataset, prompt, completion_text="test")
        PromptCompletionRating.set_rating(temp_dataset, completion, facet1, 5)
        PromptCompletionRating.set_rating(temp_dataset, completion, facet2, 7)

        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet2.id)
        assert rule.evaluate(sample, temp_dataset) is True


class TestNegatedRuleEvaluation:
    """Test evaluation of negated rules."""

    def test_negated_string_rule(self, temp_dataset):
        """
        Test negated string rule - matches when text is NOT present.
        """
        sample, _ = create_test_sample(temp_dataset, title="Sample Title")
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="NotPresent", negated=True)

        assert rule.evaluate(sample, temp_dataset) is True

    def test_negated_tag_rule(self, temp_dataset):
        """
        Test negated tag rule - matches when tag is NOT present.
        """
        tag = Tag.create(temp_dataset, "TestTag", "Description")
        temp_dataset.commit()  # Ensure tag ID is assigned
        sample, _ = create_test_sample(temp_dataset)

        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id, negated=True)
        assert rule.evaluate(sample, temp_dataset) is True

        # Add the tag - should no longer match
        sample.add_tag(temp_dataset, tag)
        temp_dataset.commit()  # Commit the tag association
        assert rule.evaluate(sample, temp_dataset) is False

    def test_negated_facet_rule(self, temp_dataset):
        """
        Test negated facet rule - matches when facet is NOT rated.
        """
        facet = Facet.create(temp_dataset, "TestFacet", "Description")
        temp_dataset.commit()  # Ensure facet ID is assigned
        sample, _ = create_test_sample(temp_dataset)

        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet.id, negated=True)
        assert rule.evaluate(sample, temp_dataset) is True


class TestRuleDisplayText:
    """Test human-readable display text for rules."""

    def test_string_rule_display(self, temp_dataset):
        """
        Test display text for string rule.
        """
        rule = FilterRule(rule_type=FilterRuleType.STRING, value="search term")
        text = rule.get_display_text(temp_dataset)

        assert text == 'Text contains "search term"'

    def test_tag_rule_display(self, temp_dataset):
        """
        Test display text for tag rule.
        """
        tag = Tag.create(temp_dataset, "ImportantTag", "Description")
        temp_dataset.commit()  # Ensure tag ID is assigned
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id)
        text = rule.get_display_text(temp_dataset)

        assert text == 'Tag "ImportantTag"'

    def test_facet_rule_display(self, temp_dataset):
        """
        Test display text for facet rule.
        """
        facet = Facet.create(temp_dataset, "Quality", "Quality facet")
        temp_dataset.commit()  # Ensure facet ID is assigned
        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet.id)
        text = rule.get_display_text(temp_dataset)

        assert text == 'Facet "Quality"'

    def test_negated_rule_display(self, temp_dataset):
        """
        Test display text for negated rule.
        """
        tag = Tag.create(temp_dataset, "Done", "Done tag")
        temp_dataset.commit()  # Ensure tag ID is assigned
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id, negated=True)
        text = rule.get_display_text(temp_dataset)

        assert text == 'NOT Tag "Done"'

    def test_tag_not_found_display(self, temp_dataset):
        """
        Test display text when referenced tag doesn't exist.
        """
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=99999)
        text = rule.get_display_text(temp_dataset)

        assert "Tag #99999" in text

    def test_facet_not_found_display(self, temp_dataset):
        """
        Test display text when referenced facet doesn't exist.
        """
        rule = FilterRule(rule_type=FilterRuleType.FACET, value=99999)
        text = rule.get_display_text(temp_dataset)

        assert "Facet #99999" in text
