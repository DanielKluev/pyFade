"""
Test suite for WidgetExportTemplate GUI component.

Tests export template creation, configuration, and navigation functionality.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox

from py_fade.dataset.facet import Facet
from py_fade.dataset.export_template import ExportTemplate
from py_fade.gui.widget_export_template import WidgetExportTemplate
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def _ensure_facets(dataset: "DatasetDatabase") -> List[Facet]:
    """
    Create test facets for export template testing.

    This creates specific facets needed for export template tests.
    """
    session = dataset.session
    if session is None:
        raise RuntimeError("Dataset session must be initialized for tests.")
    facets: List[Facet] = []
    facets.append(Facet.create(dataset, "Alpha", "Primary facet for exports"))
    facets.append(Facet.create(dataset, "Beta", "Secondary facet for exports"))
    session.flush()
    session.commit()
    return facets


def test_widget_export_template_crud_flow(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test complete CRUD operations for export templates.

    Verifies template creation, configuration with facets and models,
    and proper UI state management throughout the workflow.
    """
    facets = _ensure_facets(temp_dataset)

    caplog.set_level(logging.DEBUG, logger="WidgetExportTemplate")
    test_logger = logging.getLogger("test_widget_export_template.crud")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetExportTemplate(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    assert widget.template is None
    assert not widget.copy_button.isEnabled()
    assert not widget.delete_button.isVisible()

    widget.name_input.setText("Baseline Export")
    widget.description_input.setText("Primary dataset export")
    for index in range(widget.model_list.count()):
        item = widget.model_list.item(index)
        if item and item.text() in {"Gemma3", "Llama3"}:
            item.setCheckState(Qt.CheckState.Checked)
    qt_app.processEvents()

    # Add first facet with percentage limit
    widget.facet_selector.setCurrentIndex(widget.facet_selector.findData(facets[0].id))
    widget.add_facet_button.click()
    qt_app.processEvents()

    first_limit_combo = widget.facets_table.cellWidget(0, 1)
    assert isinstance(first_limit_combo, QComboBox)
    first_limit_combo.setCurrentIndex(first_limit_combo.findData("percentage"))
    first_limit_spin = widget.facets_table.cellWidget(0, 2)
    assert isinstance(first_limit_spin, QDoubleSpinBox)
    first_limit_spin.setValue(45.0)
    first_order_combo = widget.facets_table.cellWidget(0, 3)
    assert isinstance(first_order_combo, QComboBox)
    first_order_combo.setCurrentIndex(first_order_combo.findData("newest"))
    first_min_spin = widget.facets_table.cellWidget(0, 4)
    assert isinstance(first_min_spin, QDoubleSpinBox)
    first_min_spin.setValue(-2.5)
    first_avg_spin = widget.facets_table.cellWidget(0, 5)
    assert isinstance(first_avg_spin, QDoubleSpinBox)
    first_avg_spin.setValue(-1.0)

    # Add second facet with count limit
    widget.facet_selector.setCurrentIndex(widget.facet_selector.findData(facets[1].id))
    widget.add_facet_button.click()
    qt_app.processEvents()

    second_limit_combo = widget.facets_table.cellWidget(1, 1)
    assert isinstance(second_limit_combo, QComboBox)
    second_limit_combo.setCurrentIndex(second_limit_combo.findData("count"))
    second_limit_spin = widget.facets_table.cellWidget(1, 2)
    assert isinstance(second_limit_spin, QDoubleSpinBox)
    second_limit_spin.setValue(200)
    second_order_combo = widget.facets_table.cellWidget(1, 3)
    assert isinstance(second_order_combo, QComboBox)
    second_order_combo.setCurrentIndex(second_order_combo.findData("oldest"))

    widget.save_template()
    qt_app.processEvents()

    created_template = ExportTemplate.get_by_name(temp_dataset, "Baseline Export")
    assert created_template is not None
    assert created_template.training_type == "SFT"
    assert created_template.output_format.startswith("JSON")
    assert len(created_template.facets_json) == 2
    assert created_template.facets_json[0]["limit_type"] == "percentage"
    assert created_template.facets_json[1]["limit_type"] == "count"

    # Update training type to DPO which should auto-adjust output format
    widget.training_combo.setCurrentIndex(widget.training_combo.findData("DPO"))
    qt_app.processEvents()
    widget.save_template()
    qt_app.processEvents()

    updated_template = ExportTemplate.get_by_id(temp_dataset, created_template.id)
    assert updated_template is not None
    assert updated_template.training_type == "DPO"
    assert updated_template.output_format == "JSONL (Anthropic)"

    copied_ids: list[int] = []
    widget.template_copied.connect(lambda tpl: copied_ids.append(tpl.id))
    widget.copy_template()
    qt_app.processEvents()

    assert copied_ids, "Expected duplicate template to be created"
    copy = ExportTemplate.get_by_id(temp_dataset, copied_ids[0])
    assert copy is not None
    assert copy.name != updated_template.name
    assert copy.training_type == updated_template.training_type

    widget.delete_template()
    qt_app.processEvents()

    assert ExportTemplate.get_by_id(temp_dataset, updated_template.id) is None
    assert widget.template is None
    widget.deleteLater()
    qt_app.processEvents()


def test_navigation_creates_export_template_tab(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that navigation sidebar can create and access export template tabs.

    Verifies that clicking on export templates in the navigation opens the
    appropriate editing interface with properly loaded template data.
    """
    session = temp_dataset.session
    if session is None:
        raise RuntimeError("Dataset session must be initialized for tests.")

    facets = _ensure_facets(temp_dataset)
    template = ExportTemplate.create(
        temp_dataset,
        name="Nav Template",
        description="Template accessible from navigation sidebar",
        training_type="SFT",
        output_format="JSON",
        model_families=["Gemma3"],
        facets=[
            {
                "facet_id": facets[0].id,
                "limit_type": "count",
                "limit_value": 100,
                "order": "random",
                "min_logprob": None,
                "avg_logprob": None,
            }
        ],
    )
    session.flush()
    session.commit()

    logger = logging.getLogger("test_widget_export_template.navigation")
    logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, logger)

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    widget.sidebar.filter_panel.show_combo.setCurrentText("Export Templates")
    qt_app.processEvents()

    widget.sidebar.tree_view.item_selected.emit("export_template", template.id)
    qt_app.processEvents()

    existing_widget_id = widget._find_tab_by("export_template", template.id)  # pylint: disable=protected-access
    assert existing_widget_id is not None
    tab_info = widget.tabs[existing_widget_id]
    assert isinstance(tab_info["widget"], WidgetExportTemplate)

    widget.sidebar.tree_view.new_item_requested.emit("export_template")
    qt_app.processEvents()

    new_tab_ids = [
        (wid, info)
        for wid, info in widget.tabs.items()
        if info["type"] == "export_template" and info["id"] == 0
    ]
    assert new_tab_ids, "Expected a new export template tab to be created"
    for _, info in new_tab_ids:
        new_widget = info["widget"]
        assert isinstance(new_widget, WidgetExportTemplate)
        assert new_widget.template is None

    widget.deleteLater()
    qt_app.processEvents()
