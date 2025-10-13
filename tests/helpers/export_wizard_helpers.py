"""
Common test helpers for export wizard tests.
"""

from __future__ import annotations
import pathlib
import tempfile
from typing import TYPE_CHECKING

from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.controllers.export_controller import ExportController

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


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


def setup_facet_sample_and_completion(
    dataset: "DatasetDatabase",
    app: "pyFadeApp",
    facet_min_rating: int | None = None,
    facet_min_logprob: float | None = None,
    facet_avg_logprob: float | None = None,
) -> tuple[Facet, PromptRevision]:
    """
    Set up a facet with a sample ready for completion testing.

    This helper reduces code duplication by consolidating the common pattern
    of creating a facet, getting the mock model, and creating a sample with prompt.

    Args:
        dataset: The dataset to create entities in
        app: The pyFadeApp instance (for accessing providers_manager)
        facet_min_rating: Optional minimum rating threshold for facet
        facet_min_logprob: Optional minimum logprob threshold for facet
        facet_avg_logprob: Optional average logprob threshold for facet

    Returns:
        Tuple of (facet, prompt_revision)
    """
    # Create facet
    facet = Facet.create(
        dataset,
        "Test Facet",
        "Test facet description",
        min_rating=facet_min_rating,
        min_logprob_threshold=facet_min_logprob,
        avg_logprob_threshold=facet_avg_logprob,
    )
    dataset.commit()

    # Create sample with prompt
    prompt_rev = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    Sample.create_if_unique(dataset, "Test Sample", prompt_rev, "test_group")
    dataset.commit()

    return facet, prompt_rev


def create_and_run_export_test(
    app: "pyFadeApp",
    dataset: "DatasetDatabase",
    template: ExportTemplate,
    target_model_id: str | None = None,
) -> tuple[ExportController, pathlib.Path]:
    """
    Helper to create export controller, set output path, and prepare for export testing.

    This consolidates the common pattern of creating temp file and export controller.

    Args:
        app: The pyFadeApp instance
        dataset: The dataset to export from
        template: The export template to use
        target_model_id: Optional target model ID for export

    Returns:
        Tuple of (export_controller, temp_path) for further testing
    """
    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    # Create and configure export controller
    export_controller = ExportController(app, dataset, template, target_model_id=target_model_id)
    export_controller.set_output_path(temp_path)

    return export_controller, temp_path
