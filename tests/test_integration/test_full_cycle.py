"""
Test the full cycle of the application, going through entire user flow:
- Create a new dataset
- Create facets
- Import samples from JSONL, SFT style
- Import samples from JSONL, DPO style, setting to trust chosen pick.
- Run completions on samples
- Rate completions, different samples with different facets. Override some ratings from DPO import.
- Create export templates for SFT and DPO.
- Export dataset to JSONL for SFT and DPO.
- Verify exported JSONL files are correct and complete.

Important: This is comprehensive test of key functionality, so it should be maintained to be up to date and tested frequently.
Note to AI: **NEVER** delete this docstring. If flow changes, update this docstring to reflect current functionality keeping
style and format of original docstring.
"""
import pathlib
from typing import TYPE_CHECKING
import pytest
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.export_template import ExportTemplate
from py_fade.controllers.import_controller import ImportController
from py_fade.controllers.export_controller import ExportController


if TYPE_CHECKING:
    from py_fade.app import pyFadeApp

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
LM_EVAL_TEST_RESULT_1 = TEST_DATA_DIR / "results_2025-09-09T13-31-53.431753.json"
LM_EVAL_TEST_RESULT_2 = TEST_DATA_DIR / "results_2025-09-09T13-42-42.857006.json"

@pytest.mark.skip(reason="Work in progress, not implemented yet")
def test_full_cycle_lm_eval(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test the full cycle of the application, going through entire user flow.
    Go with case when we import two sets of lm_eval_results, from base and tuned models,
    for the same samples, and want to filter for regressions only.
    """
    assert temp_dataset.session is not None

    # Create four facets: style, safety, coding, math
    facet_math = Facet.create(temp_dataset, "Math", "Facet for math skills")
    facet_style = Facet.create(temp_dataset, "Style", "Facet for style preferences")
    facet_safety = Facet.create(temp_dataset, "Safety", "Facet for safety restrictions")
    facet_coding = Facet.create(temp_dataset, "Coding", "Facet for coding skills")
    temp_dataset.commit()
    assert facet_math.id is not None
    assert facet_style.id is not None
    assert facet_safety.id is not None
    assert facet_coding.id is not None

    facets = temp_dataset.session.query(Facet).all()
    assert len(facets) == 4

    # Set up import of samples with lm_eval_results format
    import_controller = ImportController(app_with_dataset, temp_dataset)
    source1 = import_controller.add_source(LM_EVAL_TEST_RESULT_1)
    source2 = import_controller.add_source(LM_EVAL_TEST_RESULT_2)
    assert len(import_controller.sources) == 2

    # Run data loading
    import_controller.load_sources()
    assert import_controller.total_active_records() == 6 # 3 samples in each file
    assert source1.model_id == "gemma3:12b-u1"

    # Set up regression filtering, assuming first source is tuned, second is base
    import_controller.add_filter("paired_comparison", {
        "filter_type": "new_failure", 
        "set_facet_pairwise_ranking": True, # Treat paired benchmarks as DPO signal, auto choose correct over wrong
        })
    import_controller.apply_filters()
    assert import_controller.total_active_records() == 2  # Only one new failure in tuned, correct and wrong completions

    # Finalize import settings and run import into dataset
    import_controller.set_facet(facet_math)
    import_controller.set_ratings(correct=8, incorrect=2, chosen=8, rejected=2)
    assert import_controller.import_to_dataset() == 2  # Two records imported
    assert import_controller.import_summary.imported_samples == 1 # One unique prompt
    assert import_controller.import_summary.imported_completions == 2 # Two completions total

    # Verify dataset contents
    samples = temp_dataset.session.query(Sample).all()
    assert len(samples) == 1
    completions = samples[0].completions
    assert len(completions) == 2

    # Create export template for math facet, SFT style
    facet_config = {
        "facet_id": facet_math.id,
        }
    template_sft = ExportTemplate.create(
        dataset=temp_dataset,
        name="Math SFT Export",
        description="Export for math facet, SFT style",
        model_families=["gemma3"],
        training_type="SFT",
        output_format="JSONL-ShareGPT",
        facets=[facet_config],
    )
    temp_dataset.commit()
    assert template_sft.id is not None

    # Create export controller and run export
    export_controller = ExportController(app_with_dataset, temp_dataset, template_sft)
    output_path_sft = pathlib.Path(temp_dataset.path) / "export_math_sft.jsonl"
    export_controller.set_output_path(output_path_sft)
    assert export_controller.run_export() == 1  # One sample exported
    assert output_path_sft.exists()
