"""
Tests for complex filter application to samples.

Tests for fetching samples using complex filter rules with AND logic.
"""

import pytest

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.filter_rule import FilterRule, FilterRuleType
from py_fade.dataset.sample import Sample
from py_fade.dataset.tag import Tag
from tests.helpers.data_helpers import create_test_sample, create_test_completion_with_params


class TestComplexFilterApplication:
    """Test applying complex filters to samples."""

    def test_fetch_with_no_rules_returns_all(self, temp_dataset):
        """
        Test that fetch_with_complex_filter with no rules returns all samples.
        """
        create_test_sample(temp_dataset, title="Sample 1", prompt_text="Prompt 1")
        create_test_sample(temp_dataset, title="Sample 2", prompt_text="Prompt 2")
        create_test_sample(temp_dataset, title="Sample 3", prompt_text="Prompt 3")
        temp_dataset.commit()

        samples = Sample.fetch_with_complex_filter(temp_dataset, [])
        assert len(samples) == 3

    def test_single_string_rule(self, temp_dataset):
        """
        Test filtering with a single string rule.
        """
        create_test_sample(temp_dataset, title="Important Sample", prompt_text="Prompt 1")
        create_test_sample(temp_dataset, title="Other Sample", prompt_text="Prompt 2")
        create_test_sample(temp_dataset, title="Important Task", prompt_text="Prompt 3")
        temp_dataset.commit()

        rule = FilterRule(rule_type=FilterRuleType.STRING, value="Important")
        samples = Sample.fetch_with_complex_filter(temp_dataset, [rule])

        assert len(samples) == 2
        assert all("Important" in s.title for s in samples)

    def test_single_tag_rule(self, temp_dataset):
        """
        Test filtering with a single tag rule.
        """
        tag = Tag.create(temp_dataset, "Done", "Done tag")
        temp_dataset.commit()

        sample1, _ = create_test_sample(temp_dataset, title="Sample 1", prompt_text="Prompt 1")
        sample2, _ = create_test_sample(temp_dataset, title="Sample 2", prompt_text="Prompt 2")
        sample3, _ = create_test_sample(temp_dataset, title="Sample 3", prompt_text="Prompt 3")

        sample1.add_tag(temp_dataset, tag)
        sample3.add_tag(temp_dataset, tag)
        temp_dataset.commit()

        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id)
        samples = Sample.fetch_with_complex_filter(temp_dataset, [rule])

        assert len(samples) == 2
        assert sample1 in samples
        assert sample3 in samples

    def test_single_facet_rule(self, temp_dataset):
        """
        Test filtering with a single facet rule.
        """
        facet = Facet.create(temp_dataset, "Quality", "Quality facet")
        temp_dataset.commit()

        sample1, prompt1 = create_test_sample(temp_dataset, title="Sample 1", prompt_text="Prompt 1")
        sample2, prompt2 = create_test_sample(temp_dataset, title="Sample 2", prompt_text="Prompt 2")
        sample3, _ = create_test_sample(temp_dataset, title="Sample 3", prompt_text="Prompt 3")

        comp1 = create_test_completion_with_params(temp_dataset, prompt1, completion_text="text1")
        comp2 = create_test_completion_with_params(temp_dataset, prompt2, completion_text="text2")

        PromptCompletionRating.set_rating(temp_dataset, comp1, facet, 7)
        PromptCompletionRating.set_rating(temp_dataset, comp2, facet, 8)
        temp_dataset.commit()

        rule = FilterRule(rule_type=FilterRuleType.FACET, value=facet.id)
        samples = Sample.fetch_with_complex_filter(temp_dataset, [rule])

        assert len(samples) == 2
        assert sample1 in samples
        assert sample2 in samples
        assert sample3 not in samples

    def test_multiple_rules_with_and_logic(self, temp_dataset):
        """
        Test that multiple rules are combined with AND logic.
        """
        tag = Tag.create(temp_dataset, "Done", "Done tag")
        temp_dataset.commit()

        sample1, _ = create_test_sample(temp_dataset, title="Important Sample 1", prompt_text="Prompt 1")
        sample2, _ = create_test_sample(temp_dataset, title="Important Sample 2", prompt_text="Prompt 2")
        sample3, _ = create_test_sample(temp_dataset, title="Other Sample", prompt_text="Prompt 3")

        sample1.add_tag(temp_dataset, tag)
        sample2.add_tag(temp_dataset, tag)
        temp_dataset.commit()

        rules = [FilterRule(rule_type=FilterRuleType.STRING, value="Important"), FilterRule(rule_type=FilterRuleType.TAG, value=tag.id)]

        samples = Sample.fetch_with_complex_filter(temp_dataset, rules)

        assert len(samples) == 2
        assert sample1 in samples
        assert sample2 in samples
        assert sample3 not in samples

    def test_negated_rule(self, temp_dataset):
        """
        Test filtering with a negated rule.
        """
        tag = Tag.create(temp_dataset, "WIP", "Work in progress")
        temp_dataset.commit()

        sample1, _ = create_test_sample(temp_dataset, title="Sample 1", prompt_text="Prompt 1")
        sample2, _ = create_test_sample(temp_dataset, title="Sample 2", prompt_text="Prompt 2")
        sample3, _ = create_test_sample(temp_dataset, title="Sample 3", prompt_text="Prompt 3")

        sample2.add_tag(temp_dataset, tag)
        temp_dataset.commit()

        # Find samples NOT tagged with WIP
        rule = FilterRule(rule_type=FilterRuleType.TAG, value=tag.id, negated=True)
        samples = Sample.fetch_with_complex_filter(temp_dataset, [rule])

        assert len(samples) == 2
        assert sample1 in samples
        assert sample3 in samples
        assert sample2 not in samples

    def test_complex_multi_rule_scenario(self, temp_dataset):
        """
        Test a complex scenario with multiple rules of different types.
        """
        tag_done = Tag.create(temp_dataset, "Done", "Done tag")
        tag_wip = Tag.create(temp_dataset, "WIP", "Work in progress")
        facet = Facet.create(temp_dataset, "Quality", "Quality facet")
        temp_dataset.commit()

        # Create various samples
        sample1, prompt1 = create_test_sample(temp_dataset, title="Important Task 1", prompt_text="Prompt 1")
        sample2, prompt2 = create_test_sample(temp_dataset, title="Important Task 2", prompt_text="Prompt 2")
        sample3, prompt3 = create_test_sample(temp_dataset, title="Important Task 3", prompt_text="Prompt 3")
        sample4, _ = create_test_sample(temp_dataset, title="Other Task", prompt_text="Prompt 4")

        # Add tags
        sample1.add_tag(temp_dataset, tag_done)
        sample2.add_tag(temp_dataset, tag_done)
        sample2.add_tag(temp_dataset, tag_wip)
        sample3.add_tag(temp_dataset, tag_done)
        temp_dataset.commit()

        # Add ratings
        comp1 = create_test_completion_with_params(temp_dataset, prompt1, completion_text="text1")
        comp3 = create_test_completion_with_params(temp_dataset, prompt3, completion_text="text3")
        PromptCompletionRating.set_rating(temp_dataset, comp1, facet, 8)
        PromptCompletionRating.set_rating(temp_dataset, comp3, facet, 9)
        temp_dataset.commit()

        # Filter: Important + Done + NOT WIP + has Quality facet
        rules = [
            FilterRule(rule_type=FilterRuleType.STRING, value="Important"),
            FilterRule(rule_type=FilterRuleType.TAG, value=tag_done.id),
            FilterRule(rule_type=FilterRuleType.TAG, value=tag_wip.id, negated=True),
            FilterRule(rule_type=FilterRuleType.FACET, value=facet.id),
        ]

        samples = Sample.fetch_with_complex_filter(temp_dataset, rules)

        # Only sample1 and sample3 match all criteria
        # sample1: Important + Done + NOT WIP + has Quality
        # sample2: Important + Done + WIP (fails NOT WIP) + no Quality
        # sample3: Important + Done + NOT WIP + has Quality
        # sample4: Not Important (fails first rule)
        assert len(samples) == 2
        assert sample1 in samples
        assert sample3 in samples

    def test_rules_from_dict(self, temp_dataset):
        """
        Test that rules can be provided as dictionaries.
        """
        create_test_sample(temp_dataset, title="Important Sample", prompt_text="Prompt 1")
        create_test_sample(temp_dataset, title="Other Sample", prompt_text="Prompt 2")
        temp_dataset.commit()

        rule_dict = {"type": "string", "value": "Important", "negated": False}
        samples = Sample.fetch_with_complex_filter(temp_dataset, [rule_dict])

        assert len(samples) == 1
        assert "Important" in samples[0].title

    def test_mixed_rule_and_dict_inputs(self, temp_dataset):
        """
        Test that rules can be provided as a mix of FilterRule and dict objects.
        """
        tag = Tag.create(temp_dataset, "Done", "Done tag")
        temp_dataset.commit()

        sample1, _ = create_test_sample(temp_dataset, title="Important Sample", prompt_text="Prompt 1")
        sample2, _ = create_test_sample(temp_dataset, title="Important Task", prompt_text="Prompt 2")
        sample3, _ = create_test_sample(temp_dataset, title="Other Sample", prompt_text="Prompt 3")

        sample1.add_tag(temp_dataset, tag)
        temp_dataset.commit()

        rules = [
            {
                "type": "string",
                "value": "Important",
                "negated": False
            },
            FilterRule(rule_type=FilterRuleType.TAG, value=tag.id),
        ]

        samples = Sample.fetch_with_complex_filter(temp_dataset, rules)

        assert len(samples) == 1
        assert sample1 in samples
