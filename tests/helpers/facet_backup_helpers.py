"""
Common test helpers for facet backup tests.

Shared functionality to reduce code duplication across test files.
"""

import contextlib
import hashlib
import pathlib
import tempfile
from typing import TYPE_CHECKING, Generator

from py_fade.controllers.import_controller import ImportController
from py_fade.controllers.export_controller import ExportController
from py_fade.data_formats.facet_backup import FacetBackupFormat
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


@contextlib.contextmanager
def create_temp_database() -> Generator["DatasetDatabase", None, None]:
    """
    Create a temporary database for testing.
    
    Yields:
        DatasetDatabase instance that's properly initialized and cleaned up
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
        target_db_path = pathlib.Path(db_file.name)

    try:
        from py_fade.dataset.dataset import DatasetDatabase  # pylint: disable=import-outside-toplevel
        target_dataset = DatasetDatabase(target_db_path)
        target_dataset.initialize()
        yield target_dataset
        target_dataset.dispose()
    finally:
        target_db_path.unlink(missing_ok=True)


@contextlib.contextmanager
def create_temp_backup_file(suffix: str = '.json') -> Generator[pathlib.Path, None, None]:
    """
    Create a temporary backup file for testing.
    
    Args:
        suffix: File extension to use
        
    Yields:
        Path to temporary file that's cleaned up after use
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


def create_test_completion(dataset: "DatasetDatabase", prompt_rev: PromptRevision, completion_text: str, model_id: str,
                           temperature: float = 0.7, top_k: int = 40) -> PromptCompletion:
    """
    Create a test completion with standard parameters.
    
    Args:
        dataset: Dataset to add completion to
        prompt_rev: Prompt revision for the completion
        completion_text: Text content of the completion
        model_id: Model identifier
        temperature: Sampling temperature
        top_k: Top-k sampling parameter
        
    Returns:
        Created PromptCompletion instance
    """
    sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

    completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=model_id, temperature=temperature, top_k=top_k,
                                  completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                  context_length=2048, max_tokens=512)
    dataset.session.add(completion)
    dataset.commit()
    return completion


def create_test_facet_with_data(dataset: "DatasetDatabase", facet_name: str, facet_description: str, sample_count: int = 1,
                                completions_per_sample: int = 1) -> Facet:
    """
    Create a test facet with associated samples, completions, and ratings.
    
    Args:
        dataset: Dataset to create data in
        facet_name: Name of the facet
        facet_description: Description of the facet
        sample_count: Number of samples to create
        completions_per_sample: Number of completions per sample
        
    Returns:
        Created Facet instance
    """
    facet = Facet.create(dataset, facet_name, facet_description)
    dataset.commit()

    for i in range(sample_count):
        prompt_rev = PromptRevision.get_or_create(dataset, f"{facet_name.lower()} prompt {i}", 2048, 512)
        dataset.commit()

        Sample.create_if_unique(dataset, f"{facet_name} Sample {i}", prompt_rev, f"group_{i}")
        dataset.commit()

        for j in range(completions_per_sample):
            completion = create_test_completion(dataset, prompt_rev, f"{facet_name.lower()} completion {i}-{j}", f"test-model-{j}",
                                                temperature=0.6 + j * 0.1, top_k=35 + j * 5)

            PromptCompletionRating.set_rating(dataset, completion, facet, 6 + j)

    dataset.commit()
    return facet


def export_facet_to_backup(app: "pyFadeApp", dataset: "DatasetDatabase", facet_id: int, backup_path: pathlib.Path) -> int:
    """
    Export a facet to a backup file.
    
    Args:
        app: Application instance
        dataset: Source dataset
        facet_id: ID of facet to export
        backup_path: Path to save backup file
        
    Returns:
        Number of items exported
    """
    export_controller = ExportController.create_for_facet_backup(app, dataset)
    export_controller.set_output_path(backup_path)
    return export_controller.export_facet_backup(facet_id)


def import_facet_from_backup(app: "pyFadeApp", dataset: "DatasetDatabase", backup_path: pathlib.Path,
                             merge_strategy: str = "skip_duplicates") -> int:
    """
    Import a facet from a backup file.
    
    Args:
        app: Application instance 
        dataset: Target dataset
        backup_path: Path to backup file
        merge_strategy: How to handle conflicts
        
    Returns:
        Number of items imported
    """
    import_controller = ImportController(app, dataset)
    import_controller.add_source(backup_path)
    return import_controller.import_facet_backup_to_dataset(merge_strategy)


def validate_backup_content(backup_path: pathlib.Path, expected_facet_name: str, expected_samples: int, expected_completions: int,
                            expected_ratings: int) -> None:
    """
    Validate the content of a backup file.
    
    Args:
        backup_path: Path to backup file
        expected_facet_name: Expected facet name
        expected_samples: Expected number of samples
        expected_completions: Expected number of completions
        expected_ratings: Expected number of ratings
    """
    backup_format = FacetBackupFormat(backup_path)
    backup_format.load()

    backup_data = backup_format.backup_data
    assert backup_data is not None
    assert backup_data.facet['name'] == expected_facet_name
    assert len(backup_data.samples) == expected_samples
    assert len(backup_data.completions) == expected_completions
    assert len(backup_data.ratings) == expected_ratings
