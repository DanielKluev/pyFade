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


def test_filter_selector_visibility(ensure_google_icon_font, qt_app):
    """
    Test that filter selector is visible only for 'Samples by Filter' mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show()
    qt_app.processEvents()

    # Initially hidden for "Samples by Group"
    assert not panel.filter_selector.isVisible()
    assert not panel.filter_selector_label.isVisible()

    # Visible for "Samples by Filter"
    panel.show_combo.setCurrentText("Samples by Filter")
    panel._on_show_changed()  # Manually trigger the handler
    qt_app.processEvents()
    assert panel.filter_selector.isVisible()
    assert panel.filter_selector_label.isVisible()

    # Hidden for other modes
    panel.show_combo.setCurrentText("Facets")
    panel._on_show_changed()  # Manually trigger the handler
    qt_app.processEvents()
    assert not panel.filter_selector.isVisible()
    assert not panel.filter_selector_label.isVisible()


def test_filter_panel_includes_selected_filter_id_in_criteria(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that filter panel includes selected_filter_id in criteria for 'Samples by Filter' mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

    # Create sample filters
    filter1 = SampleFilter.create(temp_dataset, "Filter1", "Test filter 1")
    filter2 = SampleFilter.create(temp_dataset, "Filter2", "Test filter 2")
    temp_dataset.commit()

    # Refresh to ensure IDs are loaded
    session = temp_dataset.get_session()
    session.refresh(filter1)
    session.refresh(filter2)

    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Samples by Filter")
    panel._on_show_changed()  # Trigger visibility update
    qt_app.processEvents()

    # Now update the filter list after selector is visible
    panel.update_filter_list(temp_dataset)
    qt_app.processEvents()

    # Verify filters were added to combo (newest first due to order_by_date=True)
    assert panel.filter_selector.count() == 2
    assert panel.filter_selector.itemText(0) == "Filter2"  # Newest first
    assert panel.filter_selector.itemText(1) == "Filter1"

    # Select first filter (Filter2)
    panel.filter_selector.setCurrentIndex(0)
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["selected_filter_id"] == filter2.id

    # Select second filter (Filter1)
    panel.filter_selector.setCurrentIndex(1)
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["selected_filter_id"] == filter1.id


def test_navigation_tree_samples_by_filter_no_filter_selected(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that navigation tree shows placeholder when no filter is selected.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Filter", "data_filter": DataFilter([]), "selected_filter_id": None}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    assert tree.tree.topLevelItemCount() == 1
    item = tree.tree.topLevelItem(0)
    assert item.text(0) == "No filter selected"


def test_navigation_tree_samples_by_filter_flat_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that navigation tree correctly shows samples filtered by a complex filter in flat mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

    # Create tag and samples
    tag = Tag.create(temp_dataset, "Important", "Important tag")
    temp_dataset.commit()

    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt a", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt b", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt c", 2048, 512)
    temp_dataset.commit()

    sample1 = Sample.create_if_unique(temp_dataset, "Sample A", prompt_rev1, "folder_x/subfolder_1")
    sample2 = Sample.create_if_unique(temp_dataset, "Sample B", prompt_rev2, "folder_x/subfolder_2")
    _sample3 = Sample.create_if_unique(temp_dataset, "Sample C", prompt_rev3, "folder_y")
    temp_dataset.commit()

    # Tag only sample1 and sample2
    add_tag_to_samples(temp_dataset, tag, [sample1, sample2])

    # Create filter that matches tagged samples
    sample_filter = SampleFilter.create(temp_dataset, "Tagged Important", "Filter for important samples", filter_rules=[{
        "type": "tag",
        "value": tag.id,
        "negated": False
    }])
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test flat mode
    criteria = {"show": "Samples by Filter", "data_filter": DataFilter([]), "flat_list_mode": True, "selected_filter_id": sample_filter.id}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have 2 samples directly as top level items (flat mode)
    assert tree.tree.topLevelItemCount() == 2
    sample_titles = {tree.tree.topLevelItem(i).text(0) for i in range(tree.tree.topLevelItemCount())}
    assert sample_titles == {"Sample A", "Sample B"}


def test_navigation_tree_samples_by_filter_hierarchical_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that navigation tree correctly shows samples filtered by a complex filter in hierarchical mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

    # Create tag and samples
    tag = Tag.create(temp_dataset, "Done", "Done tag")
    temp_dataset.commit()

    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt x", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt y", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt z", 2048, 512)
    temp_dataset.commit()

    sample1 = Sample.create_if_unique(temp_dataset, "Task A", prompt_rev1, "work/category1")
    sample2 = Sample.create_if_unique(temp_dataset, "Task B", prompt_rev2, "work/category2")
    sample3 = Sample.create_if_unique(temp_dataset, "Task C", prompt_rev3, "personal")
    temp_dataset.commit()

    # Tag all samples
    add_tag_to_samples(temp_dataset, tag, [sample1, sample2, sample3])

    # Create filter that matches all tagged samples
    sample_filter = SampleFilter.create(temp_dataset, "All Done", "Filter for done tasks", filter_rules=[{
        "type": "tag",
        "value": tag.id,
        "negated": False
    }])
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test hierarchical mode (flat_list_mode=False)
    criteria = {"show": "Samples by Filter", "data_filter": DataFilter([]), "flat_list_mode": False, "selected_filter_id": sample_filter.id}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have 2 top level items: "work" and "personal" folders
    assert tree.tree.topLevelItemCount() == 2
    folder_names = {tree.tree.topLevelItem(i).text(0) for i in range(tree.tree.topLevelItemCount())}
    assert folder_names == {"work", "personal"}


def test_group_by_rating_toggle_visibility(ensure_google_icon_font, qt_app):
    """
    Test that group by rating toggle is visible only for 'Samples by Facet' mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show()
    qt_app.processEvents()

    # Initially hidden for "Samples by Group"
    assert not panel.group_by_rating_toggle.isVisible()

    # Visible for "Samples by Facet"
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()
    qt_app.processEvents()
    assert panel.group_by_rating_toggle.isVisible()

    # Hidden for other modes
    panel.show_combo.setCurrentText("Samples by Tag")
    panel._on_show_changed()
    qt_app.processEvents()
    assert not panel.group_by_rating_toggle.isVisible()


def test_group_by_rating_toggle_disables_flat_list(ensure_google_icon_font, qt_app):
    """
    Test that enabling group by rating automatically disables flat list mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()
    qt_app.processEvents()

    # Enable flat list first
    panel.flat_list_toggle.click()
    qt_app.processEvents()
    assert panel.flat_list_toggle.is_toggled()
    assert not panel.group_by_rating_toggle.is_toggled()

    # Enable group by rating - should disable flat list
    panel.group_by_rating_toggle.click()
    qt_app.processEvents()
    assert not panel.flat_list_toggle.is_toggled()
    assert panel.group_by_rating_toggle.is_toggled()


def test_flat_list_toggle_disables_group_by_rating(ensure_google_icon_font, qt_app):
    """
    Test that enabling flat list automatically disables group by rating mode.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()
    qt_app.processEvents()

    # Enable group by rating first
    panel.group_by_rating_toggle.click()
    qt_app.processEvents()
    assert panel.group_by_rating_toggle.is_toggled()
    assert not panel.flat_list_toggle.is_toggled()

    # Enable flat list - should disable group by rating
    panel.flat_list_toggle.click()
    qt_app.processEvents()
    assert panel.flat_list_toggle.is_toggled()
    assert not panel.group_by_rating_toggle.is_toggled()


def test_filter_panel_includes_group_by_rating_mode_in_criteria(ensure_google_icon_font, qt_app):
    """
    Test that filter panel includes group_by_rating_mode in criteria.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    panel = WidgetNavigationFilterPanel()
    panel.show_combo.setCurrentText("Samples by Facet")
    panel._on_show_changed()
    qt_app.processEvents()

    # Initially not toggled
    criteria = panel.get_filter_criteria()
    assert criteria["group_by_rating_mode"] is False

    # Toggle on
    panel.group_by_rating_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["group_by_rating_mode"] is True

    # Toggle off
    panel.group_by_rating_toggle.click()
    qt_app.processEvents()
    criteria = panel.get_filter_criteria()
    assert criteria["group_by_rating_mode"] is False


def test_sample_get_highest_rating_for_facet(temp_dataset):
    """
    Test that Sample.get_highest_rating_for_facet returns the correct highest rating.
    """
    # Create a facet
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create a sample with prompt revision
    prompt_rev = PromptRevision.get_or_create(temp_dataset, "test prompt", 2048, 512)
    temp_dataset.commit()
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev)
    temp_dataset.commit()

    # Initially no ratings
    assert sample.get_highest_rating_for_facet(facet) is None

    # Create completions with different ratings
    completion1 = create_test_completion(temp_dataset, prompt_rev, "completion 1", "test-model")
    completion2 = create_test_completion(temp_dataset, prompt_rev, "completion 2", "test-model")
    completion3 = create_test_completion(temp_dataset, prompt_rev, "completion 3", "test-model")

    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 7)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 9)
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 5)
    temp_dataset.commit()

    # Should return highest rating (9)
    assert sample.get_highest_rating_for_facet(facet) == 9


def test_navigation_tree_samples_by_facet_group_by_rating_mode(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that navigation tree correctly groups samples by rating when group_by_rating_mode is True.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create samples with different ratings
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    temp_dataset.commit()

    _sample1 = Sample.create_if_unique(temp_dataset, "Sample A", prompt_rev1, "group1")
    _sample2 = Sample.create_if_unique(temp_dataset, "Sample B", prompt_rev2, "group1")
    _sample3 = Sample.create_if_unique(temp_dataset, "Sample C", prompt_rev3, "group2")
    temp_dataset.commit()

    # Create completions with ratings
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    completion3 = create_test_completion(temp_dataset, prompt_rev3, "completion 3", "test-model")

    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 10)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 10)
    temp_dataset.commit()

    tree = WidgetNavigationTree()
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([]), "flat_list_mode": False, "group_by_rating_mode": True}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have one facet at top level
    assert tree.tree.topLevelItemCount() == 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item.text(0) == "Quality"

    # Should have 2 rating groups under facet: Rating: 10 and Rating: 8
    assert facet_item.childCount() == 2

    # First rating group should be Rating: 10 with 2 samples (Sample A and Sample C)
    rating_10_item = facet_item.child(0)
    assert rating_10_item.text(0) == "Rating: 10"
    assert rating_10_item.childCount() == 2
    sample_titles_10 = {rating_10_item.child(i).text(0) for i in range(rating_10_item.childCount())}
    assert sample_titles_10 == {"Sample A", "Sample C"}

    # Second rating group should be Rating: 8 with 1 sample (Sample B)
    rating_8_item = facet_item.child(1)
    assert rating_8_item.text(0) == "Rating: 8"
    assert rating_8_item.childCount() == 1
    assert rating_8_item.child(0).text(0) == "Sample B"


def test_navigation_sidebar_persists_group_by_rating_mode(app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that group by rating mode preference is persisted and restored.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font
    _ = temp_dataset  # Dataset is opened via app_with_dataset fixture

    # Create a sidebar and toggle group by rating mode on
    sidebar1 = WidgetNavigationSidebar(None, app_with_dataset)
    sidebar1.filter_panel.show_combo.setCurrentText("Samples by Facet")
    sidebar1.filter_panel.group_by_rating_toggle.click()  # Toggle on
    qt_app.processEvents()

    # Verify it's toggled
    assert sidebar1.filter_panel.group_by_rating_toggle.is_toggled()

    # Create a new sidebar instance (simulating app restart)
    sidebar2 = WidgetNavigationSidebar(None, app_with_dataset)
    qt_app.processEvents()

    # Verify the preference was restored
    assert sidebar2.filter_panel.group_by_rating_toggle.is_toggled()

    # Toggle off and verify persistence
    sidebar2.filter_panel.group_by_rating_toggle.click()  # Toggle off
    qt_app.processEvents()
    assert not sidebar2.filter_panel.group_by_rating_toggle.is_toggled()

    # Create another sidebar instance
    sidebar3 = WidgetNavigationSidebar(None, app_with_dataset)
    qt_app.processEvents()

    # Verify the preference was restored (off state)
    assert not sidebar3.filter_panel.group_by_rating_toggle.is_toggled()


def test_navigation_tree_samples_sorted_by_title(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that samples are sorted by title in all grouping modes.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create facet
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create samples with names that would be out of order if not sorted
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt z", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt a", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt m", 2048, 512)
    temp_dataset.commit()

    _sample1 = Sample.create_if_unique(temp_dataset, "Zebra Sample", prompt_rev1)
    _sample2 = Sample.create_if_unique(temp_dataset, "Apple Sample", prompt_rev2)
    _sample3 = Sample.create_if_unique(temp_dataset, "Mango Sample", prompt_rev3)
    temp_dataset.commit()

    # Create completions with same rating
    completion1 = create_test_completion(temp_dataset, prompt_rev1, "completion 1", "test-model")
    completion2 = create_test_completion(temp_dataset, prompt_rev2, "completion 2", "test-model")
    completion3 = create_test_completion(temp_dataset, prompt_rev3, "completion 3", "test-model")

    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 8)
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test with group by rating mode
    criteria = {"show": "Samples by Facet", "data_filter": DataFilter([]), "flat_list_mode": False, "group_by_rating_mode": True}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    facet_item = tree.tree.topLevelItem(0)
    rating_item = facet_item.child(0)

    # Verify samples are sorted alphabetically
    assert rating_item.childCount() == 3
    assert rating_item.child(0).text(0) == "Apple Sample"
    assert rating_item.child(1).text(0) == "Mango Sample"
    assert rating_item.child(2).text(0) == "Zebra Sample"


def test_navigation_tree_samples_by_group_sorted_alphabetically(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that samples are sorted alphabetically within groups in "Samples by Group" mode.

    Samples should be sorted case-insensitively by title within each group node.
    Group nodes themselves should also be sorted lexicographically.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples with different group paths and titles that would be out of order if not sorted
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    prompt_rev4 = PromptRevision.get_or_create(temp_dataset, "prompt 4", 2048, 512)
    prompt_rev5 = PromptRevision.get_or_create(temp_dataset, "prompt 5", 2048, 512)
    prompt_rev6 = PromptRevision.get_or_create(temp_dataset, "prompt 6", 2048, 512)
    temp_dataset.commit()

    # Group A with samples in non-alphabetical creation order
    Sample.create_if_unique(temp_dataset, "Zebra", prompt_rev1, "Group_A")
    Sample.create_if_unique(temp_dataset, "Apple", prompt_rev2, "Group_A")
    Sample.create_if_unique(temp_dataset, "Mango", prompt_rev3, "Group_A")

    # Group B/SubGroup with samples
    Sample.create_if_unique(temp_dataset, "Yellow", prompt_rev4, "Group_B/SubGroup")
    Sample.create_if_unique(temp_dataset, "Alpha", prompt_rev5, "Group_B/SubGroup")

    # Ungrouped sample
    Sample.create_if_unique(temp_dataset, "Ungrouped Item", prompt_rev6, None)
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test Samples by Group mode
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Should have 2 top-level groups (Group_A, Group_B) plus Ungrouped
    assert tree.tree.topLevelItemCount() == 3

    # Find Group_A item
    group_a_item = None
    group_b_item = None
    ungrouped_item = None
    for i in range(tree.tree.topLevelItemCount()):
        item = tree.tree.topLevelItem(i)
        if item.text(0) == "Group_A":
            group_a_item = item
        elif item.text(0) == "Group_B":
            group_b_item = item
        elif item.text(0) == "Ungrouped":
            ungrouped_item = item

    assert group_a_item is not None, "Group_A should exist"
    assert group_b_item is not None, "Group_B should exist"
    assert ungrouped_item is not None, "Ungrouped should exist"

    # Verify samples in Group_A are sorted alphabetically
    assert group_a_item.childCount() == 3
    assert group_a_item.child(0).text(0) == "Apple"
    assert group_a_item.child(1).text(0) == "Mango"
    assert group_a_item.child(2).text(0) == "Zebra"

    # Verify Group_B has SubGroup as child
    assert group_b_item.childCount() == 1
    subgroup_item = group_b_item.child(0)
    assert subgroup_item.text(0) == "SubGroup"

    # Verify samples in SubGroup are sorted alphabetically
    assert subgroup_item.childCount() == 2
    assert subgroup_item.child(0).text(0) == "Alpha"
    assert subgroup_item.child(1).text(0) == "Yellow"

    # Verify ungrouped sample
    assert ungrouped_item.childCount() == 1
    assert ungrouped_item.child(0).text(0) == "Ungrouped Item"


def test_navigation_tree_samples_by_group_case_insensitive_sort(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that samples are sorted case-insensitively in "Samples by Group" mode.

    Samples with different cases should be sorted ignoring case.
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples with mixed case titles
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    prompt_rev4 = PromptRevision.get_or_create(temp_dataset, "prompt 4", 2048, 512)
    temp_dataset.commit()

    # Create samples with titles that differ only in case
    Sample.create_if_unique(temp_dataset, "zebra", prompt_rev1, "TestGroup")
    Sample.create_if_unique(temp_dataset, "APPLE", prompt_rev2, "TestGroup")
    Sample.create_if_unique(temp_dataset, "Banana", prompt_rev3, "TestGroup")
    Sample.create_if_unique(temp_dataset, "cherry", prompt_rev4, "TestGroup")
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test Samples by Group mode
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find TestGroup item
    test_group_item = None
    for i in range(tree.tree.topLevelItemCount()):
        item = tree.tree.topLevelItem(i)
        if item.text(0) == "TestGroup":
            test_group_item = item
            break

    assert test_group_item is not None, "TestGroup should exist"

    # Verify samples are sorted case-insensitively (APPLE, Banana, cherry, zebra)
    assert test_group_item.childCount() == 4
    assert test_group_item.child(0).text(0) == "APPLE"
    assert test_group_item.child(1).text(0) == "Banana"
    assert test_group_item.child(2).text(0) == "cherry"
    assert test_group_item.child(3).text(0) == "zebra"


def test_navigation_tree_samples_by_group_mixed_nodes_sorted(temp_dataset, ensure_google_icon_font, qt_app):
    """
    Test that both samples and subgroups are sorted together at each level.

    When a group contains both direct samples and subgroups, they should all be
    sorted alphabetically together (case-insensitive).

    Example: Chemistry group with "Sample B" and subgroup "Organic" should show:
    - Organic (subgroup)
    - Sample B (sample)
    """
    _ = ensure_google_icon_font  # Used for side effect of loading icon font

    # Create samples that will result in mixed children (samples + subgroups) at same level
    prompt_rev1 = PromptRevision.get_or_create(temp_dataset, "prompt 1", 2048, 512)
    prompt_rev2 = PromptRevision.get_or_create(temp_dataset, "prompt 2", 2048, 512)
    prompt_rev3 = PromptRevision.get_or_create(temp_dataset, "prompt 3", 2048, 512)
    prompt_rev4 = PromptRevision.get_or_create(temp_dataset, "prompt 4", 2048, 512)
    prompt_rev5 = PromptRevision.get_or_create(temp_dataset, "prompt 5", 2048, 512)
    temp_dataset.commit()

    # Chemistry group will have: "Zebra Sample" (sample), "Organic" (subgroup), "Apple Sample" (sample)
    Sample.create_if_unique(temp_dataset, "Zebra Sample", prompt_rev1, "Chemistry")
    Sample.create_if_unique(temp_dataset, "Benzene", prompt_rev2, "Chemistry/Organic")
    Sample.create_if_unique(temp_dataset, "Apple Sample", prompt_rev3, "Chemistry")
    Sample.create_if_unique(temp_dataset, "NaCl", prompt_rev4, "Chemistry/Inorganic")
    Sample.create_if_unique(temp_dataset, "Mango Sample", prompt_rev5, "Chemistry")
    temp_dataset.commit()

    tree = WidgetNavigationTree()

    # Test Samples by Group mode
    criteria = {"show": "Samples by Group", "data_filter": DataFilter([])}
    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    # Find Chemistry item
    chemistry_item = None
    for i in range(tree.tree.topLevelItemCount()):
        item = tree.tree.topLevelItem(i)
        if item.text(0) == "Chemistry":
            chemistry_item = item
            break

    assert chemistry_item is not None, "Chemistry group should exist"

    # Chemistry should have 5 children: 3 samples + 2 subgroups
    assert chemistry_item.childCount() == 5

    # Children should be sorted alphabetically (case-insensitive):
    # 1. Apple Sample (sample)
    # 2. Inorganic (subgroup)
    # 3. Mango Sample (sample)
    # 4. Organic (subgroup)
    # 5. Zebra Sample (sample)
    assert chemistry_item.child(0).text(0) == "Apple Sample"
    assert chemistry_item.child(1).text(0) == "Inorganic"
    assert chemistry_item.child(2).text(0) == "Mango Sample"
    assert chemistry_item.child(3).text(0) == "Organic"
    assert chemistry_item.child(4).text(0) == "Zebra Sample"

    # Verify that subgroups have their samples
    inorganic_item = chemistry_item.child(1)
    assert inorganic_item.childCount() == 1
    assert inorganic_item.child(0).text(0) == "NaCl"

    organic_item = chemistry_item.child(3)
    assert organic_item.childCount() == 1
    assert organic_item.child(0).text(0) == "Benzene"
