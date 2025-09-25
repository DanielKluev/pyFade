from __future__ import annotations

import pytest

from py_fade.dataset.facet import Facet


def test_create_and_lookup_facet(temp_dataset):
    facet = Facet.create(temp_dataset, "Data Quality", "Evaluate inputs and outputs")
    temp_dataset.commit()

    assert facet.id is not None
    fetched_by_name = Facet.get_by_name(temp_dataset, "Data Quality")
    fetched_by_id = Facet.get_by_id(temp_dataset, facet.id)

    assert fetched_by_name is not None
    assert fetched_by_id is not None
    assert fetched_by_name.id == facet.id
    assert fetched_by_id.description == "Evaluate inputs and outputs"


def test_unique_facet_name_enforced(temp_dataset):
    Facet.create(temp_dataset, "Response Coherence", "Track flow")
    temp_dataset.commit()

    with pytest.raises(ValueError):
        Facet.create(temp_dataset, "Response Coherence", "Duplicate name disallowed")


def test_update_and_delete_facet(temp_dataset):
    facet = Facet.create(temp_dataset, "Factual Accuracy", "Initial description")
    temp_dataset.commit()

    facet.update(temp_dataset, name="Factual Rigour", description="Updated details")
    temp_dataset.commit()

    updated = Facet.get_by_id(temp_dataset, facet.id)
    assert updated is not None
    assert updated.name == "Factual Rigour"
    assert updated.description == "Updated details"

    updated.delete(temp_dataset)
    temp_dataset.commit()

    assert Facet.get_by_id(temp_dataset, facet.id) is None


def test_get_all_orders_by_latest_first(temp_dataset):
    first = Facet.create(temp_dataset, "Creative Writing", "Writing skills")
    temp_dataset.commit()
    second = Facet.create(temp_dataset, "Code Generation", "Coding abilities")
    temp_dataset.commit()

    facets = Facet.get_all(temp_dataset)

    assert [facet.id for facet in facets] == [second.id, first.id]