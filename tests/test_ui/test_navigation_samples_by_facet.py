"""
Test Samples By Facet navigation feature.
"""
# pylint: disable=protected-access,unused-variable
from __future__ import annotations

from PyQt6.QtCore import Qt

from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationTree
from tests.helpers.facet_backup_helpers import create_test_completion


def count_samples_recursive(item):
    """Helper function to recursively count sample items in a tree."""
    count = 0
    for j in range(item.childCount()):
        child = item.child(j)
        if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
            count += 1
        else:
            count += count_samples_recursive(child)
    return count


def find_sample_item(item):
    """Helper function to recursively find a sample item in a tree."""
    for i in range(item.childCount()):
        child = item.child(i)
        if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
            return child
        result = find_sample_item(child)
        if result:
            return result
    return None


def test_facet_get_samples_returns_associated_samples(temp_dataset):
    """Test that Facet.get_samples returns samples with rated completions."""
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()

    # Create sample with completion
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    # Create completion and rating
    completion = create_test_completion(temp_dataset, prompt_rev, "test completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Test get_samples
    samples = facet.get_samples(temp_dataset)
    assert len(samples) == 1
    assert samples[0].id == sample.id
    assert samples[0].title == "Test Sample"


def test_facet_get_samples_returns_empty_for_unrated_facet(temp_dataset):
    """Test that Facet.get_samples returns empty list when no samples are rated."""
    # Create facet without any ratings
    facet = Facet.create(temp_dataset, "Empty Facet", "No ratings")
    temp_dataset.commit()

    samples = facet.get_samples(temp_dataset)
    assert len(samples) == 0


def test_facet_get_samples_without_facet(temp_dataset):
    """Test that get_samples_without_facet returns samples with no ratings."""
    # Create sample without ratings
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "unrated prompt", 2048, 512)
    temp_dataset.commit()
    unrated_sample = Sample.create_if_unique(temp_dataset, "Unrated Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    # Create facet and sample with rating
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "rated prompt", 2048, 512)
    temp_dataset.commit()
    rated_sample = Sample.create_if_unique(temp_dataset, "Rated Sample", prompt_rev2, "group_2")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev2, "rated completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 7)

    # Test get_samples_without_facet
    samples_without_facet = Facet.get_samples_without_facet(temp_dataset)
    assert len(samples_without_facet) == 1
    assert samples_without_facet[0].id == unrated_sample.id


def test_populate_samples_by_facet_basic(temp_dataset, ensure_google_icon_font, qt_app):
    """Test basic population of samples by facet."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet with sample
    facet = Facet.create(temp_dataset, "Facet A", "Description A")
    temp_dataset.commit()
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "prompt for facet A", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Sample A", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "completion A", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 9)

    # Create tree and populate
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have at least the facet node
    assert tree.tree.topLevelItemCount() >= 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item is not None
    assert facet_item.text(0) == "Facet A"


def test_populate_samples_by_facet_with_groups(temp_dataset, ensure_google_icon_font, qt_app):
    """Test samples by facet respects group_path hierarchy."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet
    facet = Facet.create(temp_dataset, "Facet B", "Description B")
    temp_dataset.commit()

    # Create samples with hierarchical group paths
    for i, group_path in enumerate(["group_1/subgroup_a", "group_1/subgroup_b", "group_2"]):
        prompt_rev = PromptRevision.get_or_create(temp_dataset, f"prompt {i}", 2048, 512)
        temp_dataset.commit()
        sample = Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, group_path)
        temp_dataset.commit()
        completion = create_test_completion(temp_dataset, prompt_rev, f"completion {i}", "test-model")
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Create tree and populate
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have the facet node
    assert tree.tree.topLevelItemCount() >= 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item.text(0) == "Facet B"

    # Facet should have child nodes for groups
    assert facet_item.childCount() > 0


def test_populate_samples_by_facet_no_facet_node(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that samples without facet appear under 'No Facet' node."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample without any ratings
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "unrated prompt", 2048, 512)
    temp_dataset.commit()
    Sample.create_if_unique(temp_dataset, "Unrated Sample", prompt_rev, "group_x")
    temp_dataset.commit()

    # Create tree and populate
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have "No Facet" node
    assert tree.tree.topLevelItemCount() >= 1
    no_facet_item = tree.tree.topLevelItem(0)
    assert no_facet_item is not None
    assert no_facet_item.text(0) == "No Facet"


def test_populate_samples_by_facet_multiple_facets(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that samples appear under multiple facets if rated for multiple facets."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create two facets
    facet1 = Facet.create(temp_dataset, "Facet 1", "Description 1")
    facet2 = Facet.create(temp_dataset, "Facet 2", "Description 2")
    temp_dataset.commit()

    # Create sample with completions rated for both facets
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "multi-facet prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Multi-Facet Sample", prompt_rev, "shared_group")
    temp_dataset.commit()

    completion1 = create_test_completion(temp_dataset, prompt_rev, "completion 1", "test-model-1")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet1, 8)

    completion2 = create_test_completion(temp_dataset, prompt_rev, "completion 2", "test-model-2")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet2, 7)

    # Create tree and populate
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have both facet nodes
    assert tree.tree.topLevelItemCount() >= 2

    # Find sample under both facets
    sample_count = 0
    for i in range(tree.tree.topLevelItemCount()):
        facet_item = tree.tree.topLevelItem(i)
        if facet_item.text(0) in ["Facet 1", "Facet 2"]:
            # Check if sample is under this facet
            if facet_item.childCount() > 0:
                # Navigate through group hierarchy to find samples
                sample_count += count_samples_recursive(facet_item)

    # Sample should appear under both facets
    assert sample_count == 2


def test_populate_samples_by_facet_with_search_filter(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that search filter works with samples by facet view."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facets with samples
    facet1 = Facet.create(temp_dataset, "Important Facet", "Description 1")
    facet2 = Facet.create(temp_dataset, "Other Facet", "Description 2")
    temp_dataset.commit()

    # Create samples
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "important prompt", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Important Sample", prompt_rev1, "group_1")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet1, 8)

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "other prompt", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Other Sample", prompt_rev2, "group_2")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet2, 7)

    # Create tree and populate with search filter
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should only have "Important Facet" in tree
    assert tree.tree.topLevelItemCount() >= 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item is not None
    assert "Important" in facet_item.text(0)


def test_sample_items_have_correct_data(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that sample items have correct UserRole data for selection."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet with sample
    facet = Facet.create(temp_dataset, "Data Test Facet", "Description")
    temp_dataset.commit()
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "data test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Data Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "data test completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 9)

    # Create tree and populate
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find sample item
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item is not None

    # Navigate to find sample item
    sample_item = find_sample_item(facet_item)
    assert sample_item is not None
    assert sample_item.data(0, Qt.ItemDataRole.UserRole) == "sample"
    assert sample_item.data(1, Qt.ItemDataRole.UserRole) == sample.id
