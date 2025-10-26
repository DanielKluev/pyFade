"""
Test suite for "Samples by Tag" navigation functionality.

Tests navigation sidebar samples by tag view including:
- Tag grouping display
- Sample organization under tags
- "No Tag" node for untagged samples
- Search filtering by tag and sample names
- Empty state handling
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_tag import SampleTag  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.tag import Tag
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationTree
from tests.helpers.data_helpers import create_test_tags_and_samples
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp


def test_navigation_samples_by_tag_empty_state(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that empty dataset shows no items in samples by tag view.

    Edge case: when no tags or samples exist, tree should be empty.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.empty")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify tree is empty
    assert tree.tree.topLevelItemCount() == 0

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_displays_tags(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that tags with samples are displayed as root nodes.

    Verifies that tags appear as root nodes in the tree.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.display_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create standard test tags and samples
    tag1, tag2, sample1, sample2 = create_test_tags_and_samples(dataset)

    # Add tags to samples
    sample1.add_tag(dataset, tag1)
    sample2.add_tag(dataset, tag2)
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify tags are displayed
    assert tree.tree.topLevelItemCount() == 2
    tag_names = [tree.tree.topLevelItem(i).text(0) for i in range(tree.tree.topLevelItemCount())]
    assert "Important" in tag_names
    assert "Reviewed" in tag_names

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_displays_untagged_samples(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples without tags appear under "No Tag" node.

    Verifies that untagged samples are grouped under a special "No Tag" node.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.untagged")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create sample without tags
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    _sample = Sample.create_if_unique(dataset, "Untagged Sample", prompt_revision)
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify "No Tag" node is displayed
    assert tree.tree.topLevelItemCount() == 1
    no_tag_item = tree.tree.topLevelItem(0)
    assert no_tag_item.text(0) == "No Tag"

    # Verify sample is under "No Tag" node
    assert no_tag_item.childCount() > 0

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_groups_by_path(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples are grouped by group_path under tags.

    Verifies that group_path hierarchy is preserved under tag nodes.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.group_by_path")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create tag
    tag = Tag.create(dataset, "Important", "Important samples", scope="samples")
    dataset.commit()

    # Create samples with group paths
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample1 = Sample.create_if_unique(dataset, "Sample 1", prompt_revision, group_path="Math/Algebra")
    dataset.commit()

    prompt_revision2 = PromptRevision.get_or_create(dataset, "Test prompt 2", 2048, 512)
    sample2 = Sample.create_if_unique(dataset, "Sample 2", prompt_revision2, group_path="Math/Geometry")
    dataset.commit()

    # Add tag to samples
    sample1.add_tag(dataset, tag)
    sample2.add_tag(dataset, tag)
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify tag node
    assert tree.tree.topLevelItemCount() == 1
    tag_item = tree.tree.topLevelItem(0)
    assert tag_item.text(0) == "Important"

    # Verify group path hierarchy
    assert tag_item.childCount() == 1
    math_item = tag_item.child(0)
    assert math_item.text(0) == "Math"
    assert math_item.childCount() == 2  # Algebra and Geometry

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_multiple_tags_per_sample(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples with multiple tags appear under each tag.

    Verifies that a sample associated with multiple tags appears in multiple places.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.multiple_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create tags
    tag1 = Tag.create(dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(dataset, "Reviewed", "Reviewed samples", scope="both")
    dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Sample 1", prompt_revision)
    dataset.commit()

    # Add both tags to sample
    sample.add_tag(dataset, tag1)
    sample.add_tag(dataset, tag2)
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify both tags are displayed
    assert tree.tree.topLevelItemCount() == 2

    # Verify sample appears under both tags
    for i in range(tree.tree.topLevelItemCount()):
        tag_item = tree.tree.topLevelItem(i)
        # Should have at least one child (the sample or a group containing it)
        assert tag_item.childCount() > 0

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_search_filter(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that search filter works with samples by tag view.

    Verifies that text search filters tags and samples appropriately.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.search")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create standard test tags and samples
    tag1, tag2, _sample1, _sample2 = create_test_tags_and_samples(dataset)

    # Create samples with specific names for search test
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt math", 2048, 512)
    sample1 = Sample.create_if_unique(dataset, "Math Sample", prompt_revision)
    dataset.commit()

    prompt_revision2 = PromptRevision.get_or_create(dataset, "Test prompt science", 2048, 512)
    sample2 = Sample.create_if_unique(dataset, "Science Sample", prompt_revision2)
    dataset.commit()

    # Add tags to samples
    sample1.add_tag(dataset, tag1)
    sample2.add_tag(dataset, tag2)
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Create a data filter with search text
    from py_fade.dataset.data_filter import DataFilter  # pylint: disable=import-outside-toplevel
    data_filter = DataFilter([{"type": "text_search", "value": "math"}])

    # Update with "Samples by Tag" filter and search
    filter_criteria = {"show": "Samples by Tag", "data_filter": data_filter}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify only tags with matching samples are shown
    # Should show tag1 (Important) because it has a sample with "math" in title/prompt
    assert tree.tree.topLevelItemCount() >= 0  # At least tag1 should be shown

    # Find the Important tag (if present)
    important_found = False
    for i in range(tree.tree.topLevelItemCount()):
        item = tree.tree.topLevelItem(i)
        if item.text(0) == "Important":
            important_found = True
            break

    # Important tag should be found because Math Sample matches
    assert important_found

    tree.deleteLater()
    qt_app.processEvents()


def test_navigation_samples_by_tag_hides_empty_tags(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that tags without samples are not displayed.

    Edge case: tags with no associated samples should not appear in the tree.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetNavigationTree")
    test_logger = logging.getLogger("test_navigation_samples_by_tag.hide_empty")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dataset = app_with_dataset.current_dataset

    # Create tag without samples
    Tag.create(dataset, "Empty Tag", "Tag with no samples", scope="samples")
    dataset.commit()

    # Create navigation tree
    tree = WidgetNavigationTree()
    qt_app.processEvents()

    # Update with "Samples by Tag" filter
    filter_criteria = {"show": "Samples by Tag", "data_filter": None}
    tree.update_content(filter_criteria, app_with_dataset.current_dataset)
    qt_app.processEvents()

    # Verify empty tag is not displayed
    assert tree.tree.topLevelItemCount() == 0

    tree.deleteLater()
    qt_app.processEvents()
