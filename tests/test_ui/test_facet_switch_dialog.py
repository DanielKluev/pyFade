"""
Test suite for FacetSwitchDialog UI component.

Tests facet switching dialog functionality including:
- Dialog initialization and display
- Action selection (Remove, Change, Copy)
- Target facet selection
- Integration with FacetSwitchController
- UI feedback and validation
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.dialog_facet_switch import FacetSwitchDialog
from tests.helpers.data_helpers import create_test_completion_pair
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase


def test_facet_switch_dialog_initialization(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test initializing the facet switch dialog.

    Verifies that the dialog is properly initialized with sample and facet information.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.initialization")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    facet2 = Facet.create(temp_dataset, "Accuracy", "Accuracy facet")  # pylint: disable=unused-variable
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Verify dialog properties
    assert dialog.sample == sample
    assert dialog.source_facet == facet1
    assert dialog.dataset == temp_dataset
    assert "Quality" in dialog.windowTitle()

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_loads_target_facets(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that dialog loads target facets correctly.

    Verifies that all facets except the source facet are loaded into the combo box.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.load_facets")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    Facet.create(temp_dataset, "Accuracy", "Accuracy facet")  # facet2 - for combo box
    Facet.create(temp_dataset, "Clarity", "Clarity facet")  # facet3 - for combo box
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Verify target combo contains facet2 and facet3, but not facet1
    combo_items = [dialog.target_combo.itemText(i) for i in range(dialog.target_combo.count())]
    assert "Accuracy" in combo_items
    assert "Clarity" in combo_items
    assert "Quality" not in combo_items

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_default_action_is_remove(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that the default action is remove.

    Verifies that the remove radio button is checked by default.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.default_action")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Verify remove is default
    assert dialog.remove_radio.isChecked()
    assert not dialog.change_radio.isChecked()
    assert not dialog.copy_radio.isChecked()
    # Target combo should be disabled for remove action
    assert not dialog.target_combo.isEnabled()

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_change_action_enables_combo(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that selecting change action enables target combo.

    Verifies that the target facet combo is enabled when change is selected.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.change_action")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    facet2 = Facet.create(temp_dataset, "Accuracy", "Accuracy facet")  # pylint: disable=unused-variable
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Select change action
    dialog.change_radio.setChecked(True)
    qt_app.processEvents()

    # Verify combo is enabled
    assert dialog.target_combo.isEnabled()
    assert "will be moved" in dialog.info_label.text().lower()

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_remove_action_with_confirmation(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test removing a facet with confirmation dialog.

    Verifies that the remove action calls the controller and shows confirmation.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.remove_action")
    test_logger.setLevel(logging.DEBUG)

    # Mock message boxes
    message_box_mock = MagicMock()
    # Return the Yes button value directly, not a MagicMock
    from PyQt6.QtWidgets import QMessageBox as RealQMessageBox  # pylint: disable=import-outside-toplevel
    message_box_mock.question.return_value = RealQMessageBox.StandardButton.Yes
    message_box_mock.information.return_value = None
    message_box_mock.StandardButton = RealQMessageBox.StandardButton
    monkeypatch.setattr("py_fade.gui.dialog_facet_switch.QMessageBox", message_box_mock)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample with ratings
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    completion = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion, facet1, 8)

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Select remove action (already default)
    assert dialog.remove_radio.isChecked()

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify confirmation was shown
    assert message_box_mock.question.called
    # Verify info message was shown
    assert message_box_mock.information.called

    # Verify rating was removed
    assert PromptCompletionRating.get(temp_dataset, completion, facet1) is None

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_change_action(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test changing facet action.

    Verifies that the change action transfers ratings to the target facet.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.change_action_exec")
    test_logger.setLevel(logging.DEBUG)

    # Mock message boxes
    message_box_mock = MagicMock()
    message_box_mock.information.return_value = None
    monkeypatch.setattr("py_fade.gui.dialog_facet_switch.QMessageBox", message_box_mock)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    facet2 = Facet.create(temp_dataset, "Accuracy", "Accuracy facet")
    temp_dataset.commit()

    # Create sample with ratings
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    completion = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion, facet1, 8)

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Select change action
    dialog.change_radio.setChecked(True)
    qt_app.processEvents()

    # Select target facet (facet2 should be at index 0)
    dialog.target_combo.setCurrentIndex(0)
    assert dialog.target_combo.currentText() == "Accuracy"

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify info message was shown
    assert message_box_mock.information.called

    # Verify rating was moved
    assert PromptCompletionRating.get(temp_dataset, completion, facet1) is None
    target_rating = PromptCompletionRating.get(temp_dataset, completion, facet2)
    assert target_rating is not None
    assert target_rating.rating == 8

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_copy_action(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test copying facet action.

    Verifies that the copy action duplicates ratings to the target facet.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.copy_action_exec")
    test_logger.setLevel(logging.DEBUG)

    # Mock message boxes
    message_box_mock = MagicMock()
    message_box_mock.information.return_value = None
    monkeypatch.setattr("py_fade.gui.dialog_facet_switch.QMessageBox", message_box_mock)

    # Create facets
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    facet2 = Facet.create(temp_dataset, "Accuracy", "Accuracy facet")
    temp_dataset.commit()

    # Create sample with ratings
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    completion = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion, facet1, 8)

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Select copy action
    dialog.copy_radio.setChecked(True)
    qt_app.processEvents()

    # Select target facet
    dialog.target_combo.setCurrentIndex(0)
    assert dialog.target_combo.currentText() == "Accuracy"

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify info message was shown
    assert message_box_mock.information.called

    # Verify rating was copied (original still exists)
    source_rating = PromptCompletionRating.get(temp_dataset, completion, facet1)
    assert source_rating is not None
    assert source_rating.rating == 8

    target_rating = PromptCompletionRating.get(temp_dataset, completion, facet2)
    assert target_rating is not None
    assert target_rating.rating == 8

    dialog.deleteLater()
    qt_app.processEvents()


def test_facet_switch_dialog_no_other_facets_disables_actions(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that change/copy actions are disabled when no other facets exist.

    Edge case: when only one facet exists, change and copy should be disabled.
    """
    caplog.set_level(logging.DEBUG, logger="FacetSwitchDialog")
    test_logger = logging.getLogger("test_facet_switch_dialog.no_other_facets")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create only one facet
    facet1 = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = FacetSwitchDialog(temp_dataset, sample, facet1)
    qt_app.processEvents()

    # Verify change and copy are disabled
    assert not dialog.change_radio.isEnabled()
    assert not dialog.copy_radio.isEnabled()
    # Remove should still be enabled
    assert dialog.remove_radio.isEnabled()

    dialog.deleteLater()
    qt_app.processEvents()
