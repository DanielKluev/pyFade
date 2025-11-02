"""
Test Widgets test module.
"""
# pylint: disable=protected-access
from __future__ import annotations

from PyQt6.QtCore import Qt

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.dataset.tag import Tag
from py_fade.gui.widget_navigation_sidebar import (
    WidgetNavigationFilterPanel,
    WidgetNavigationSidebar,
    WidgetNavigationTree,
)
from tests.helpers.data_helpers import add_tag_to_samples
from tests.helpers.facet_backup_helpers import create_test_completion


def test_filter_panel_builds_text_search_filter(ensure_google_icon_font, qt_app):
    """Test that filter panel correctly builds text search filters."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.search_input.setText("  Important  ")
    qt_app.processEvents()

    criteria = panel.get_filter_criteria()

    assert criteria["show"] == "Samples by Group"
    assert criteria["data_filter"].filters == [{"type": "text_search", "value": "important"}]


def test_filter_panel_flat_list_toggle_visibility(ensure_google_icon_font, qt_app):
    """Test that flat list toggle is visible only for tag/facet groupings."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show()  # Make sure the panel itself is visible
    qt_app.processEvents()

    # Initially hidden for "Samples by Group"
    assert not panel.flat_list_toggle.isVisible()

    # Visible for "Samples by Facet"
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()  # Manually trigger the handler to ensure it's called
    qt_app.processEvents()
    assert panel.flat_list_toggle.isVisible()

    # Visible for "Samples by Tag"
    panel.show_combo.setCurrentText("Samples by Tag")
    panel._on_show_changed()  # Manually trigger the handler to ensure it's called
    qt_app.processEvents()
    assert panel.flat_list_toggle.isVisible()

    # Hidden for other modes
    panel.show_combo.setCurrentText("Facets")
    panel._on_show_changed()  # Manually trigger the handler to ensure it's called
    qt_app.processEvents()
    assert not panel.flat_list_toggle.isVisible()


def test_filter_panel_includes_flat_list_mode_in_criteria(ensure_google_icon_font, qt_app):
    """Test that filter panel includes flat_list_mode in criteria."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Samples by Tag")
    qt_app.processEvents()

    # Initially not toggled
    criteria = panel.get_filter_criteria()
    assert criteria["flat_list_mode"] is False

    # Toggle on
    panel.flat_list_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["flat_list_mode"] is True

    # Toggle off
    panel.flat_list_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["flat_list_mode"] is False


def test_navigation_tree_lists_facets(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that navigation tree correctly lists facets from the dataset."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    Facet.create(temp_dataset, "Evaluation", "Primary facet")
    temp_dataset.commit()

    tree = WidgetNavigationTree()
    criteria = {
        "show": "Facets",
        "data_filter": temp_dataset,  # placeholder, replaced below
    }
    # Replace placeholder with empty DataFilter.
    criteria["data_filter"] = DataFilter([])

    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    assert tree.tree.topLevelItemCount() == 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item is not None
    assert facet_item.text(0) == "Evaluation"
    assert facet_item.data(0, Qt.ItemDataRole.UserRole) == "facet"


def test_navigation_tree_samples_by_facet_flat_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that navigation tree lists samples flat under facets when flat_list_mode is True."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet and samples with group paths
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    temp_dataset.commit()

    _sample1 = Sample.create_if_unique(temp_dataset, "Sample 1", prompt_rev1, "group_a/subgroup_1")
    _sample2 = Sample.create_if_unique(temp_dataset, "Sample 2", prompt_rev2, "group_a/subgroup_2")
    _sample3 = Sample.create_if_unique(temp_dataset, "Sample 3", prompt_rev3, "group_b")
    temp_dataset.commit()

    # Create completions and ratings to associate samples with facet
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    completion3 = create_test_completion(temp_dataset, prompt_rev3, "completion 3", "test-model")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 5)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 4)
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 3)
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test hierarchical mode (flat_list_mode=False)
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([]), "flat_list_mode": False}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have facet as top level item
    assert tree.tree.topLevelItemCount() == 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item.text(0) == "Quality"
    # Should have group_a and group_b as children
    assert facet_item.childCount() == 2

    # Test flat mode (flat_list_mode=True)
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([]), "flat_list_mode": True}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have facet as top level item
    assert tree.tree.topLevelItemCount() == 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item.text(0) == "Quality"
    # Should have 3 samples directly as children (no group hierarchy)
    assert facet_item.childCount() == 3
    # Check samples are listed
    sample_titles = {facet_item.child(i).text(0) for i in range(facet_item.childCount())}
    assert sample_titles == {"Sample 1", "Sample 2", "Sample 3"}


def test_navigation_tree_samples_by_tag_flat_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """Test that navigation tree lists samples flat under tags when flat_list_mode is True."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create tag and samples with group paths
    tag = Tag.create(temp_dataset, "Important", "Important samples", scope="both")
    temp_dataset.commit()

    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt a", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt b", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt c", 2048, 512)
    temp_dataset.commit()

    sample1 = Sample.create_if_unique(temp_dataset, "Sample A", prompt_rev1, "folder_x/subfolder_1")
    sample2 = Sample.create_if_unique(temp_dataset, "Sample B", prompt_rev2, "folder_x/subfolder_2")
    sample3 = Sample.create_if_unique(temp_dataset, "Sample C", prompt_rev3, "folder_y")
    temp_dataset.commit()

    # Add tags to samples
    add_tag_to_samples(temp_dataset, tag, [sample1, sample2, sample3])

    tree = WidgetNavigationTree()

    # Test hierarchical mode (flat_list_mode=False)
    criteria = {"show": "Samples by Tag", "data_filter": DataFilter([]), "flat_list_mode": False}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have tag as top level item
    assert tree.tree.topLevelItemCount() == 1
    tag_item = tree.tree.topLevelItem(0)
    assert tag_item.text(0) == "Important"
    # Should have folder_x and folder_y as children
    assert tag_item.childCount() == 2

    # Test flat mode (flat_list_mode=True)
    criteria = {"show": "Samples by Tag", "data_filter": DataFilter([]), "flat_list_mode": True}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have tag as top level item
    assert tree.tree.topLevelItemCount() == 1
    tag_item = tree.tree.topLevelItem(0)
    assert tag_item.text(0) == "Important"
    # Should have 3 samples directly as children (no group hierarchy)
    assert tag_item.childCount() == 3
    # Check samples are listed
    sample_titles = {tag_item.child(i).text(0) for i in range(tag_item.childCount())}
    assert sample_titles == {"Sample A", "Sample B", "Sample C"}


def test_navigation_sidebar_emits_selection(app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
    """Test that navigation sidebar correctly emits selection events."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    # Ensure a facet exists so the sidebar initialises correctly.
    facet = Facet.create(temp_dataset, "Context", "Sidebar facet")
    temp_dataset.commit()

    selections: list[tuple[str, int]] = []
    sidebar = WidgetNavigationSidebar(None, app_with_dataset)
    sidebar.item_selected.connect(lambda item_type, item_id: selections.append((item_type, item_id)))
    sidebar.filter_panel.show_combo.setCurrentText("Facets")
    qt_app.processEvents()
    qt_app.processEvents()

    tree_item = sidebar.tree_view.tree.topLevelItem(0)
    assert tree_item is not None
    sidebar.tree_view._on_item_clicked(tree_item, 0)
    qt_app.processEvents()

    assert selections
    item_type, item_id = selections[-1]
    assert item_type in {"sample", "facet"}
    if item_type == "facet":
        assert item_id == facet.id


def test_navigation_sidebar_persists_flat_list_mode(app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
    """Test that flat list mode preference is persisted and restored."""
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    _ = temp_dataset  # Dataset is opened via app_with_dataset fixture, but not directly used in test

    # Create a sidebar and toggle flat list mode on
    sidebar1 = WidgetNavigationSidebar(None, app_with_dataset)
    sidebar1.filter_panel.show_combo.setCurrentText("Samples by Tag")
    sidebar1.filter_panel.flat_list_toggle.click()  # Toggle on
    qt_app.processEvents()

    # Verify it's toggled
    assert sidebar1.filter_panel.flat_list_toggle.is_toggled()

    # Create a new sidebar instance (simulating app restart or navigation)
    sidebar2 = WidgetNavigationSidebar(None, app_with_dataset)
    qt_app.processEvents()

    # Verify the preference was restored
    assert sidebar2.filter_panel.flat_list_toggle.is_toggled()

    # Toggle off and verify persistence
    sidebar2.filter_panel.flat_list_toggle.click()  # Toggle off
    qt_app.processEvents()
    assert not sidebar2.filter_panel.flat_list_toggle.is_toggled()

    # Create another sidebar instance
    sidebar3 = WidgetNavigationSidebar(None, app_with_dataset)
    qt_app.processEvents()

    # Verify the preference was restored (off state)
    assert not sidebar3.filter_panel.flat_list_toggle.is_toggled()
