"""
Test navigation panel completions search functionality.
"""
# pylint: disable=protected-access,unused-variable
from __future__ import annotations

from PyQt6.QtCore import Qt

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationFilterPanel, WidgetNavigationTree
from tests.helpers.facet_backup_helpers import create_test_completion


def test_completions_search_option_available(ensure_google_icon_font, qt_app):
    """
    Test that "Completions Search" option is available in the show combo box.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    panel = WidgetNavigationFilterPanel()
    qt_app.processEvents()

    # Check that "Completions Search" is in the combo box
    options = [panel.show_combo.itemText(i) for i in range(panel.show_combo.count())]
    assert "Completions Search" in options


def test_completions_search_top_rated_toggle_visibility(ensure_google_icon_font, qt_app):
    """
    Test that top rated only toggle is visible only for "Completions Search".
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    panel = WidgetNavigationFilterPanel()
    panel.show()
    qt_app.processEvents()

    # Initially hidden for "Samples by Group"
    assert not panel.top_rated_only_toggle.isVisible()

    # Visible for "Completions Search"
    panel.show_combo.setCurrentText("Completions Search")
    panel._on_show_changed()
    qt_app.processEvents()
    assert panel.top_rated_only_toggle.isVisible()

    # Hidden for other modes
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()
    qt_app.processEvents()
    assert not panel.top_rated_only_toggle.isVisible()


def test_completions_search_includes_top_rated_only_in_criteria(ensure_google_icon_font, qt_app):
    """
    Test that filter panel includes top_rated_only in criteria.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Completions Search")
    qt_app.processEvents()

    # Initially not toggled
    criteria = panel.get_filter_criteria()
    assert criteria["top_rated_only"] is False

    # Toggle on
    panel.top_rated_only_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["top_rated_only"] is True

    # Toggle off
    panel.top_rated_only_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["top_rated_only"] is False


def test_completions_search_shows_placeholder_when_no_query(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search shows a placeholder message when no search query is provided.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with completion
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "test completion text", "test-model")

    # Create tree and populate with empty search
    tree = WidgetNavigationTree()
    criteria = {"show": "Completions Search", "data_filter": DataFilter([]), "top_rated_only": False}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should show placeholder message
    assert tree.tree.topLevelItemCount() == 1
    top_item = tree.tree.topLevelItem(0)
    assert "Enter search query" in top_item.text(0)


def test_completions_search_finds_samples_with_matching_completions(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search finds samples with matching completion text.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with completion containing "important"
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample One", prompt_rev1, "group_1")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "This is an important completion", "test-model")

    # Create sample with completion NOT containing "important"
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample Two", prompt_rev2, "group_1")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "This is a regular completion", "test-model")

    # Search for "important"
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "important"
        }]),
        "top_rated_only": False
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find only Sample One
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Sample One" in found_samples


def test_completions_search_is_case_insensitive(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search is case-insensitive.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with completion in mixed case
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "This is IMPORTANT text", "test-model")

    # Search with lowercase
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "important"
        }]),
        "top_rated_only": False
    }
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
    assert "Test Sample" in found_samples


def test_completions_search_searches_all_completions(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search finds samples if ANY completion matches (not just first).
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with multiple completions, only one containing "special"
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev, "First completion text", "test-model")
    completion2 = create_test_completion(temp_dataset, prompt_rev, "Second completion with special word", "test-model")
    completion3 = create_test_completion(temp_dataset, prompt_rev, "Third completion text", "test-model")

    # Search for "special"
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "special"
        }]),
        "top_rated_only": False
    }
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
    assert "Test Sample" in found_samples


def test_completions_search_top_rated_only_searches_highest_rated(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that with top_rated_only enabled, only the highest-rated completion is searched.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet for ratings
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample with multiple completions
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    # Low-rated completion with "important"
    completion1 = create_test_completion(temp_dataset, prompt_rev, "Low rated important completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 3)

    # High-rated completion without "important"
    completion2 = create_test_completion(temp_dataset, prompt_rev, "High rated regular completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 9)

    # Search for "important" with top_rated_only enabled
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "important"
        }]),
        "top_rated_only": True
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should NOT find the sample (highest rated doesn't have "important")
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 0


def test_completions_search_top_rated_only_finds_match_in_top_rated(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that with top_rated_only enabled, samples are found if top-rated completion matches.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet for ratings
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample with multiple completions
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()

    # Low-rated completion without "important"
    completion1 = create_test_completion(temp_dataset, prompt_rev, "Low rated regular completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 3)

    # High-rated completion with "important"
    completion2 = create_test_completion(temp_dataset, prompt_rev, "High rated important completion", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 9)

    # Search for "important" with top_rated_only enabled
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "important"
        }]),
        "top_rated_only": True
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find the sample (highest rated has "important")
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Test Sample" in found_samples


def test_completions_search_skips_samples_without_completions(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that samples without completions are skipped in completions search.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample without completions
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample Without Completions", prompt_rev1, "group_1")
    temp_dataset.commit()

    # Create sample with completion
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample With Completion", prompt_rev2, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev2, "test completion", "test-model")

    # Search for "test"
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "test"
        }]),
        "top_rated_only": False
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should find only sample with completion
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 1
    assert "Sample With Completion" in found_samples


def test_completions_search_shows_no_results_message(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search shows appropriate message when no matches found.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with completion
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "This is a test completion", "test-model")

    # Search for non-existent text
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "nonexistent"
        }]),
        "top_rated_only": False
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should show "no results" message
    assert tree.tree.topLevelItemCount() == 1
    top_item = tree.tree.topLevelItem(0)
    assert "No completions found" in top_item.text(0)


def test_completions_search_groups_samples_by_group_path(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that completions search groups samples by their group_path.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples in different groups with matching completions
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    temp_dataset.commit()
    sample1 = Sample.create_if_unique(temp_dataset, "Sample in Group A", prompt_rev1, "GroupA")
    temp_dataset.commit()
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "match text", "test-model")

    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    temp_dataset.commit()
    sample2 = Sample.create_if_unique(temp_dataset, "Sample in Group B", prompt_rev2, "GroupB")
    temp_dataset.commit()
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "match text", "test-model")

    # Search for "match"
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "match"
        }]),
        "top_rated_only": False
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have two top-level groups
    assert tree.tree.topLevelItemCount() == 2

    # Collect group names
    group_names = [tree.tree.topLevelItem(i).text(0) for i in range(tree.tree.topLevelItemCount())]
    assert "GroupA" in group_names
    assert "GroupB" in group_names


def test_completions_search_top_rated_only_with_no_ratings(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that with top_rated_only enabled, samples without ratings are not shown.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create sample with completion but no ratings
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "group_1")
    temp_dataset.commit()
    completion = create_test_completion(temp_dataset, prompt_rev, "important completion", "test-model")

    # Search for "important" with top_rated_only enabled
    tree = WidgetNavigationTree()
    criteria = {
        "show": "Completions Search",
        "data_filter": DataFilter([{
            "type": "text_search",
            "value": "important"
        }]),
        "top_rated_only": True
    }
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should NOT find the sample (no ratings)
    found_samples = []
    for i in range(tree.tree.topLevelItemCount()):
        top_item = tree.tree.topLevelItem(i)
        for j in range(top_item.childCount()):
            child = top_item.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == "sample":
                found_samples.append(child.text(0))

    assert len(found_samples) == 0
