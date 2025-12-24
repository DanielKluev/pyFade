"""
Test navigation panel search functionality.
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


def test_search_samples_by_group_filters_by_title(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search filters samples by title in "Samples by Group" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples with different titles
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Important Sample", prompt_rev1, "group_1")
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Regular Sample", prompt_rev2, "group_1")
    temp_dataset.commit()

    # Create tree and populate with search filter
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should only show "Important Sample"
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Important" in found_samples[0]


def test_search_samples_by_group_filters_by_prompt_text(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search filters samples by prompt text in "Samples by Group" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples with different prompt texts
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "This is a special prompt about cats", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample A", prompt_rev1, "group_1")
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "This is about dogs", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample B", prompt_rev2, "group_1")
    temp_dataset.commit()

    # Create tree and populate with search filter for "cats"
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "cats"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should only show "Sample A" (with prompt about cats)
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Sample A" in found_samples


def test_search_samples_by_group_case_insensitive(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search is case-insensitive in "Samples by Group" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with mixed-case title
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "prompt text", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "IMPORTANT Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    # Search with lowercase
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find the sample
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1


def test_search_samples_by_group_matches_title_or_prompt(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search matches either title OR prompt text in "Samples by Group" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples: one with "test" in title, one with "test" in prompt
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "regular prompt", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev1, "group_1")
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "this is a test prompt", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Another Sample", prompt_rev2, "group_1")
    temp_dataset.commit()

    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "unrelated prompt", 2048, 512)
    temp_dataset.commit()
    sample3 = Sample.create_if_unique(temp_dataset, "Different Sample", prompt_rev3, "group_1")
    temp_dataset.commit()

    # Search for "test"
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "test"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find both Sample 1 (title match) and Sample 2 (prompt match), but not Sample 3
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 2
    assert "Test Sample" in found_samples
    assert "Another Sample" in found_samples
    assert "Different Sample" not in found_samples


def test_search_prompts_filters_by_text(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search filters prompts by prompt text in "Prompts" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create prompts with different texts
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "This is an important prompt", 2048, 512)
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "This is a regular prompt", 2048, 512)
    temp_dataset.commit()

    # Create tree and populate with search filter
    tree = WidgetNavigationTree()
    criteria = {"show": "Prompts", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should only show the prompt with "important"
    found_prompts = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "prompt":
                found_prompts.append(child.text(0))

    assert len(found_prompts) == 1
    assert "important" in found_prompts[0]


def test_search_prompts_case_insensitive(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search is case-insensitive for prompts.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create prompt with mixed-case text
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "This is IMPORTANT text", 2048, 512)
    temp_dataset.commit()

    # Search with lowercase
    tree = WidgetNavigationTree()
    criteria = {"show": "Prompts", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find the prompt
    found_prompts = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "prompt":
                found_prompts.append(child.text(0))

    assert len(found_prompts) == 1


def test_search_samples_by_facet_filters_samples_by_title_and_prompt(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search in "Samples by Facet" view filters samples by both title and prompt text.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Description")
    temp_dataset.commit()

    # Create sample with "important" in title
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "regular prompt", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Important Sample", prompt_rev1, "group_1")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 8)

    # Create sample with "important" in prompt
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "important prompt text", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Regular Sample", prompt_rev2, "group_1")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)

    # Create sample without "important"
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "different prompt", 2048, 512)
    temp_dataset.commit()
    sample3 = Sample.create_if_unique(temp_dataset, "Other Sample", prompt_rev3, "group_1")
    temp_dataset.commit()
    completion3 = create_test_completion(temp_dataset, prompt_rev3, "completion 3", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 8)

    # Search for "important"
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([{"type": "text_search", "value": "important"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find all samples in the tree
    found_samples = []

    def collect_samples(item):
        """Helper to recursively collect sample items."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))
            else:
                collect_samples(child)

    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        collect_samples(top_item)

    # Should find samples 1 and 2 but not 3
    assert len(found_samples) == 2
    assert "Important Sample" in found_samples
    assert "Regular Sample" in found_samples
    assert "Other Sample" not in found_samples


def test_search_empty_string_shows_all(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that empty search string shows all items.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create multiple samples
    for i in range(3):
        prompt_rev = PromptRevision.get_or_create(temp_dataset, f"prompt {i}", 2048, 512)
        temp_dataset.commit()
        Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "group_1")
        temp_dataset.commit()

    # Search with empty string
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": ""}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should show all samples
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 3


def test_search_whitespace_only_shows_all(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that whitespace-only search string shows all items.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create multiple samples
    for i in range(3):
        prompt_rev = PromptRevision.get_or_create(temp_dataset, f"prompt {i}", 2048, 512)
        temp_dataset.commit()
        Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "group_1")
        temp_dataset.commit()

    # Search with whitespace only
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "   "}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should show all samples
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 3


def test_search_all_view_types_do_not_crash(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that all view types handle search without crashing.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create some test data
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    tree = WidgetNavigationTree()
    search_filter = DataFilter([{"type": "text_search", "value": "test"}])

    # Test all view types
    view_types = ["Samples by Group", "Samples by Facet", "Samples by Tag", "Facets", "Tags", "Prompts", "Export Templates"]

    for view_type in view_types:
        criteria = {"show": view_type, "data_filter": search_filter}
        # Should not crash
        tree.update_content(criteria, temp_dataset)
        qt_app.processEvents()


def test_search_samples_by_id_finds_exact_match(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that search filters samples by ID when search value is a valid integer.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create multiple samples
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample One", prompt_rev1, "group_1")
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample Two", prompt_rev2, "group_1")
    temp_dataset.commit()

    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    temp_dataset.commit()
    sample3 = Sample.create_if_unique(temp_dataset, "Sample Three", prompt_rev3, "group_1")
    temp_dataset.commit()

    # Search for sample2's ID
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": str(sample2.id)}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should only show sample2
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Sample Two" in found_samples


def test_search_samples_by_id_does_not_match_partial_id(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that ID search matches exactly, not partially (unlike text search).
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples with IDs that will likely be multi-digit
    samples = []
    for i in range(5):
        prompt_rev = PromptRevision.get_or_create(temp_dataset, f"prompt {i}", 2048, 512)
        temp_dataset.commit()
        sample = Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "group_1")
        temp_dataset.commit()
        samples.append(sample)

    # Search for a non-existent ID (like 999)
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "999"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find no samples (assuming no sample has ID 999)
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 0


def test_search_samples_by_id_or_text_matches_both(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that when search value is a valid integer, it matches both ID and text fields.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create a sample with "123" in the title
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt text", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample with 123 in title", prompt_rev1, "group_1")
    temp_dataset.commit()

    # Create another sample with "123" in the prompt
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt with 123 in text", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Another Sample", prompt_rev2, "group_1")
    temp_dataset.commit()

    # Create a third sample (will get some ID)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "different prompt", 2048, 512)
    temp_dataset.commit()
    sample3 = Sample.create_if_unique(temp_dataset, "Different Sample", prompt_rev3, "group_1")
    temp_dataset.commit()

    # Search for "123" - should match sample1 (title), sample2 (prompt), and potentially sample3 (if its ID is 123)
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "123"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find at least sample1 and sample2
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    # At minimum, should find the two samples with "123" in title/prompt
    assert len(found_samples) >= 2
    assert "Sample with 123 in title" in found_samples
    assert "Another Sample" in found_samples


def test_search_samples_by_id_in_facet_view(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that ID search works in "Samples by Facet" view.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet with a name that doesn't contain numbers
    facet = Facet.create(temp_dataset, "Quality Facet", "High quality responses")
    temp_dataset.commit()

    # Create samples with prompts and groups that won't match the ID search
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "first prompt text", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample Alpha", prompt_rev1, "group_alpha")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion alpha", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 8)

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "second prompt text", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample Beta", prompt_rev2, "group_beta")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion beta", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)

    # Search for sample1's ID in facet view
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([{"type": "text_search", "value": str(sample1.id)}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find all samples in the tree
    found_samples = []

    def collect_samples(item):
        """Helper to recursively collect sample items."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))
            else:
                collect_samples(child)

    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        collect_samples(top_item)

    # Should find only sample1
    assert len(found_samples) == 1
    assert "Sample Alpha" in found_samples


def test_search_samples_by_id_with_flat_list_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that ID search works correctly with flat list mode enabled.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Description")
    temp_dataset.commit()

    # Create samples
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample One", prompt_rev1, "group_1")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 8)

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample Two", prompt_rev2, "group_2")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)

    # Search for sample2's ID with flat list mode
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Samples by Facet",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": str(sample2.id)
        }]),
        "flat_list_mode": True
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find all samples in the tree
    found_samples = []

    def collect_samples(item):
        """Helper to recursively collect sample items."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))
            else:
                collect_samples(child)

    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        collect_samples(top_item)

    # Should find only sample2
    assert len(found_samples) == 1
    assert "Sample Two" in found_samples


def test_search_samples_non_numeric_does_not_trigger_id_search(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that non-numeric search values don't trigger ID search.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample with abc", prompt_rev1, "group_1")
    temp_dataset.commit()

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Different Sample", prompt_rev2, "group_1")
    temp_dataset.commit()

    # Search for "abc" (non-numeric)
    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([{"type": "text_search", "value": "abc"}])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find sample1 (has "abc" in title)
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Sample with abc" in found_samples
