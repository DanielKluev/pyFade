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
Note to AI: **NEVER** delete this docstring. If flow changes, update this docstring to reflect current functionality keeping style and format of original docstring.
"""
import pathlib
from typing import TYPE_CHECKING
import pytest
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.controllers.import_controller import ImportController

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
LM_EVAL_TEST_RESULT_1 = TEST_DATA_DIR / "results_2025-09-09T13-31-53.431753.json"
LM_EVAL_TEST_RESULT_2 = TEST_DATA_DIR / "results_2025-09-09T13-42-42.857006.json"

@pytest.mark.skip(reason="Work in progress, not implemented yet")
def test_full_cycle(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase"):
    """
    Test the full cycle of the application, going through entire user flow.
    """
    assert temp_dataset.session is not None

    # Create four facets: style, safety, coding, math
    facet_math = Facet.create(temp_dataset, "Math", "Facet for math skills")
    facet_style = Facet.create(temp_dataset, "Style", "Facet for style preferences")
    facet_safety = Facet.create(temp_dataset, "Safety", "Facet for safety restrictions")
    facet_coding = Facet.create(temp_dataset, "Coding", "Facet for coding skills")
    temp_dataset.commit()

    facets = temp_dataset.session.query(Facet).all()
    assert len(facets) == 4

    # Set up import of samples with lm_eval_results format
    import_controller = ImportController(app_with_dataset, temp_dataset)
    import_controller.add_source(LM_EVAL_TEST_RESULT_1)
    import_controller.add_source(LM_EVAL_TEST_RESULT_2)

    assert len(import_controller.sources) == 2