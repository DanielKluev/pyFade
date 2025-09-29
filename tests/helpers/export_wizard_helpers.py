"""
Common test helpers for export wizard tests.
"""

from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet


def create_test_template(temp_dataset):
    """Helper function to create a test facet and export template."""
    facet = Facet.create(temp_dataset, "Test Facet", "Test facet description")
    temp_dataset.commit()

    template = ExportTemplate.create(dataset=temp_dataset, name="Test Template", description="Test template description",
                                     model_families=["Gemma3"], training_type="SFT", output_format="JSONL (ShareGPT)", facets=[{
                                         "facet_id": facet.id,
                                         "limit_type": "count",
                                         "limit_value": 100,
                                         "order": "random"
                                     }])
    temp_dataset.commit()
    return facet, template
