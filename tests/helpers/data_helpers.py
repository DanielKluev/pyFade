"""
Database and data setup helpers for testing.
"""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import tempfile
from typing import TYPE_CHECKING, List, Tuple

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.providers.llm_response import LLMResponse
from py_fade.data_formats.base_data_classes import (CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs,
                                                    SinglePositionToken)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase

# Backward compatibility alias for tests
SinglePositionTokenLogprobs = SinglePositionToken


def create_test_single_position_token(token_str: str, logprob: float, token_id: int | None = None) -> SinglePositionToken:
    """
    Create a test SinglePositionToken from simple inputs.

    Helper for tests that need to create token data without dealing with all the details.
    """
    if token_id is None:
        token_id = hash(token_str) % 100000  # Use hash as dummy token_id
    return SinglePositionToken(
        token_id=token_id,
        token_str=token_str,
        token_bytes=token_str.encode("utf-8"),
        logprob=logprob,
        span=len(token_str),
    )


def ensure_test_facets(dataset: "DatasetDatabase") -> List[Facet]:
    """
    Create standard test facets in the dataset if they don't exist.

    Returns a list of facets that can be used in tests for consistent behavior.
    """
    facet_specs = [("Reasoning", "Logical reasoning and problem-solving capability"), ("Creativity", "Creative and imaginative responses"),
                   ("Safety", "Safe and appropriate content generation"), ("Accuracy", "Factual accuracy and correctness")]

    facets = []
    for name, description in facet_specs:
        facet = Facet.get_by_name(dataset, name)
        if not facet:
            facet = Facet(name=name, description=description)
            dataset.session.add(facet)
            dataset.session.commit()
        facets.append(facet)

    return facets


def create_test_completion(session, prompt_revision, completion_overrides=None):
    """
    Create a test PromptCompletion with common defaults.

    This helper eliminates duplicate completion creation code across test files.
    """
    completion_text = completion_overrides.get("completion_text", "Test completion") if completion_overrides else "Test completion"
    sha256_hash = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

    completion_defaults = {
        "prompt_revision": prompt_revision,
        "model_id": "test-model",
        "temperature": 0.7,
        "top_k": 40,
        "sha256": sha256_hash,
        "prefill": "",
        "beam_token": "",
        "completion_text": completion_text,
        "tags": None,
        "context_length": 2048,
        "max_tokens": 128,
        "is_truncated": False,
        "is_archived": False,
    }
    if completion_overrides:
        completion_defaults.update(completion_overrides)
        # Regenerate hash if completion_text was overridden
        if "completion_text" in completion_overrides:
            completion_defaults["sha256"] = hashlib.sha256(completion_defaults["completion_text"].encode("utf-8")).hexdigest()

    completion = PromptCompletion(**completion_defaults)
    session.add(completion)
    session.commit()

    return completion


def build_sample_with_completion(
    dataset: "DatasetDatabase",
    **completion_overrides,
) -> Tuple[Sample, PromptCompletion]:
    """Create a persisted sample with a single completion for tests."""
    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 128)
    sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion_text = "This is a test completion response."
    completion_overrides_local = {
        "temperature": 0.7,
        "top_k": 40,
        "completion_text": completion_text,
        "sha256": hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
    }
    completion_overrides_local.update(completion_overrides)

    completion = create_test_completion(session, prompt_revision, completion_overrides_local)

    return sample, completion


def create_test_llm_response(**overrides) -> LLMResponse:
    """Create a test LLMResponse for beam mode testing."""
    defaults = {
        "model_id": "test-beam-model",
        "prompt_conversation": CommonConversation([CommonMessage(role="user", content="Test prompt")]),
        "completion_text": "This is a beam response with some content",
        "generated_part_text": "This is a beam response with some content",
        "temperature": 0.0,
        "top_k": 1,
        "context_length": 1024,
        "max_tokens": 100,
        "prefill": None,
        "beam_token": None,
        "is_truncated": False,
    }

    # Handle logprobs conversion from list to CommonCompletionLogprobs
    if "logprobs" in overrides and isinstance(overrides["logprobs"], list):
        logprobs_list = overrides["logprobs"]
        # Convert list of SinglePositionToken to CompletionTokenLogprobs
        sampled_logprobs = CompletionTokenLogprobs(logprobs_list)
        alternative_logprobs = CompletionTopLogprobs()  # Empty for test data
        overrides["logprobs"] = CommonCompletionLogprobs(logprobs_model_id=overrides.get("model_id", defaults["model_id"]),
                                                         sampled_logprobs=sampled_logprobs, alternative_logprobs=alternative_logprobs)

    defaults.update(overrides)
    return LLMResponse(**defaults)


def setup_beam_heatmap_test(dataset: "DatasetDatabase", qt_app) -> Tuple["CompletionFrame", "MockLLMProvider"]:
    """
    Set up a beam mode CompletionFrame with heatmap functionality for testing.
    
    Returns the configured frame and mock provider for further testing.
    """
    # Import here to avoid circular imports
    from py_fade.gui.components.widget_completion import CompletionFrame  # pylint: disable=import-outside-toplevel
    from py_fade.providers.providers_manager import MappedModel  # pylint: disable=import-outside-toplevel
    from py_fade.providers.mock_provider import MockLLMProvider  # pylint: disable=import-outside-toplevel

    beam = create_test_llm_response(
        completion_text="Hello world",
        logprobs=[create_test_single_position_token("Hello", -0.1),
                  create_test_single_position_token(" world", -0.8)])
    beam.is_full_response_logprobs = True

    frame = CompletionFrame(dataset, beam, display_mode="beam")

    # Set target model to enable heatmap
    mock_provider = MockLLMProvider()
    test_model = MappedModel("test-beam-model", mock_provider)
    frame.set_target_model(test_model)

    frame.show()
    qt_app.processEvents()

    return frame, mock_provider


def create_llm_response_with_logprobs(model_id: str, completion_text: str, scored_logprob_value: float) -> LLMResponse:
    """
    Create a LLMResponse with specific scored_logprob value.

    Helper to reduce code duplication in sorting tests.
    Scored logprob is calculated as: min_logprob + avg_logprob * 2
    """
    # Create minimal logprobs that result in the desired scored_logprob
    target_logprob = scored_logprob_value / 3.0

    # Use the actual completion text as the token to avoid validation errors
    sampled_logprobs = CompletionTokenLogprobs([
        SinglePositionToken(token_id=0, token_str=completion_text, token_bytes=completion_text.encode('utf-8'), logprob=target_logprob,
                            span=1),
    ])
    alternative_logprobs = CompletionTopLogprobs([[]])

    return LLMResponse(
        model_id=model_id, prompt_conversation=[], completion_text=completion_text, generated_part_text=completion_text, temperature=0.7,
        top_k=40, context_length=1024, max_tokens=128, logprobs=CommonCompletionLogprobs(logprobs_model_id=model_id,
                                                                                         sampled_logprobs=sampled_logprobs,
                                                                                         alternative_logprobs=alternative_logprobs))


def create_simple_llm_response(model_id: str, completion_text: str) -> LLMResponse:
    """
    Create a simple LLMResponse without logprobs.

    Helper for sorting tests when logprobs are not needed.
    """
    return LLMResponse(model_id=model_id, prompt_conversation=[], completion_text=completion_text, generated_part_text=completion_text,
                       temperature=0.7, top_k=40, context_length=1024, max_tokens=128)


def create_mock_widget_sample(app, dataset):
    """
    Create a mock WidgetSample for testing NewCompletionFrame.
    
    This helper creates a minimal mock that has the required attributes
    (prompt_area, context_length_field, max_tokens_field) for NewCompletionFrame tests.
    """
    from PyQt6.QtWidgets import QWidget, QSpinBox  # pylint: disable=import-outside-toplevel
    from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit  # pylint: disable=import-outside-toplevel

    mock_widget = QWidget()
    mock_widget.app = app
    mock_widget.dataset = dataset

    # Create required attributes
    mock_widget.prompt_area = PlainTextEdit(mock_widget)
    mock_widget.prompt_area.setPlainText("Test prompt for completion generation")

    mock_widget.context_length_field = QSpinBox(mock_widget)
    mock_widget.context_length_field.setValue(2048)

    mock_widget.max_tokens_field = QSpinBox(mock_widget)
    mock_widget.max_tokens_field.setValue(128)

    return mock_widget


def create_test_sample(temp_dataset, title: str = "Test Sample", notes: str = "Test sample", prompt_text: str = "Test prompt"):
    """
    Create a sample with a prompt revision for testing.

    Returns tuple of (sample, prompt).
    """
    sample = Sample(title=title, notes=notes, date_created=datetime.datetime.now())
    temp_dataset.session.add(sample)
    prompt = PromptRevision.new_from_text(prompt_text, context_length=2048, max_tokens=100)
    temp_dataset.session.add(prompt)
    sample.prompt_revision = prompt
    temp_dataset.session.flush()
    return sample, prompt


def create_test_completion_with_params(temp_dataset, prompt, model_id: str = "test-model", completion_text: str = "Test completion",
                                       sha256: str | None = None, temperature: float = 0.7, top_k: int = 50, context_length: int = 2048,
                                       max_tokens: int = 100, is_truncated: bool = False):
    """
    Create a test PromptCompletion with explicit parameters.

    Eliminates duplicate completion creation code across test files.
    """
    if sha256 is None:
        sha256 = "a" * 64
    completion = PromptCompletion(prompt_revision_id=prompt.id, sha256=sha256, model_id=model_id, temperature=temperature, top_k=top_k,
                                  completion_text=completion_text, context_length=context_length, max_tokens=max_tokens,
                                  is_truncated=is_truncated)
    temp_dataset.session.add(completion)
    temp_dataset.session.flush()
    return completion


def create_test_logprobs(temp_dataset, completion_id: int, model_id: str, min_logprob: float, avg_logprob: float):
    """
    Create test logprobs for a completion.

    Eliminates duplicate logprobs creation code across test files.
    """
    # Create simple sampled logprobs
    sampled_logprobs_list = [
        create_test_single_position_token("Test", min_logprob).to_dict(),
        create_test_single_position_token(" completion", avg_logprob).to_dict()
    ]

    # Create empty alternative logprobs for simplicity
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())

    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
    logprobs = PromptCompletionLogprobs(prompt_completion_id=completion_id, logprobs_model_id=model_id, sampled_logprobs=None,
                                        sampled_logprobs_json=sampled_logprobs_list, alternative_logprobs=None,
                                        alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=min_logprob, avg_logprob=avg_logprob)
    # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
    temp_dataset.session.add(logprobs)
    return logprobs


def create_completion_with_rating_and_logprobs(dataset: "DatasetDatabase", prompt_revision: PromptRevision, completion_text: str,
                                               model_id: str, facet: Facet, rating: int, min_logprob: float,
                                               avg_logprob: float) -> PromptCompletion:
    """
    Create a completion with rating and logprobs for testing.

    This helper eliminates duplicate completion creation code across test files.
    Returns the created PromptCompletion.
    """
    sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

    completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_revision.id, model_id=model_id, temperature=0.7, top_k=40,
                                  completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                  context_length=2048, max_tokens=512)
    dataset.session.add(completion)
    dataset.commit()

    # Add rating
    PromptCompletionRating.set_rating(dataset, completion, facet, rating)
    dataset.commit()

    # Add logprobs
    create_test_logprobs(dataset, completion.id, model_id, min_logprob, avg_logprob)
    dataset.commit()

    return completion


def create_test_sample_with_completion(temp_dataset, facet, rating: int, min_logprob: float, avg_logprob: float, title: str = "Test Sample",
                                       notes: str = "Test sample", prompt_text: str = "Test prompt",
                                       completion_text: str = "Test completion", model_id: str = "mock-echo-model"):
    """
    Create a sample with a rated completion and logprobs for testing.

    This is a comprehensive helper that creates the full sample -> prompt -> completion -> rating -> logprobs chain.
    Returns tuple of (sample, completion).
    """
    # Create sample and prompt
    sample, prompt = create_test_sample(temp_dataset, title, notes, prompt_text)

    # Create completion with rating and logprobs using shared helper
    completion = create_completion_with_rating_and_logprobs(temp_dataset, prompt, completion_text, model_id, facet, rating, min_logprob,
                                                            avg_logprob)

    return sample, completion


def create_test_tags_and_samples(dataset: "DatasetDatabase") -> tuple:
    """
    Create standard test tags and samples for tests that need tagged sample setup.

    This is a reusable helper to avoid code duplication in tests that set up
    the same tag and sample structure.

    Returns:
        Tuple of (tag1, tag2, sample1, sample2) where:
        - tag1: Tag named "Important" with scope="samples"
        - tag2: Tag named "Reviewed" with scope="both"
        - sample1: Sample titled "Sample 1" with prompt "Test prompt"
        - sample2: Sample titled "Sample 2" with prompt "Test prompt 2"
    """
    from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel

    # Create tags
    tag1 = Tag.create(dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(dataset, "Reviewed", "Reviewed samples", scope="both")
    dataset.commit()

    # Create samples
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample1 = Sample.create_if_unique(dataset, "Sample 1", prompt_revision)
    dataset.commit()

    prompt_revision2 = PromptRevision.get_or_create(dataset, "Test prompt 2", 2048, 512)
    sample2 = Sample.create_if_unique(dataset, "Sample 2", prompt_revision2)
    dataset.commit()

    return tag1, tag2, sample1, sample2


def create_samples_with_tag(dataset: "DatasetDatabase", tag, sample_titles: list[str] | None = None) -> list[Sample]:
    """
    Create multiple samples and add them to a tag.

    This helper reduces code duplication when tests need to set up samples with a specific tag.

    Args:
        dataset: Dataset to create samples in
        tag: Tag to add to all samples
        sample_titles: List of sample titles. If None, creates 3 samples with default titles.

    Returns:
        List of created samples
    """
    if sample_titles is None:
        sample_titles = ["Sample 1", "Sample 2", "Sample 3"]

    samples = []
    for i, title in enumerate(sample_titles, 1):
        prompt_revision = PromptRevision.get_or_create(dataset, f"Test prompt {i}", 2048, 512)
        sample = Sample.create_if_unique(dataset, title, prompt_revision)
        dataset.commit()
        samples.append(sample)

    # Add tag to all samples
    for sample in samples:
        sample.add_tag(dataset, tag)
    dataset.commit()

    return samples


def add_tag_to_samples(dataset: "DatasetDatabase", tag, samples: list[Sample]) -> None:
    """
    Add a tag to multiple samples.

    This helper reduces code duplication when tests need to tag existing samples.

    Args:
        dataset: Dataset containing samples
        tag: Tag to add to all samples
        samples: List of samples to tag
    """
    for sample in samples:
        sample.add_tag(dataset, tag)
    dataset.commit()


def create_test_completion_pair(temp_dataset: "DatasetDatabase", prompt_revision: PromptRevision, sha256_1: str = "a" * 64,
                                sha256_2: str = "b" * 64, completion_text_1: str = "Test completion 1",
                                completion_text_2: str = "Test completion 2", **kwargs) -> tuple[PromptCompletion, PromptCompletion]:
    """
    Create a pair of test completions with common defaults.

    This helper eliminates the duplicate code pattern of creating two similar completions
    that appears frequently in tests.

    Args:
        temp_dataset: Dataset to add completions to
        prompt_revision: PromptRevision to associate completions with
        sha256_1: SHA256 for first completion
        sha256_2: SHA256 for second completion
        completion_text_1: Text for first completion
        completion_text_2: Text for second completion
        **kwargs: Additional parameters to override defaults (applied to both completions)

    Returns:
        Tuple of (completion1, completion2)
    """
    defaults = {"model_id": "test-model", "temperature": 0.7, "top_k": 50, "context_length": 2048, "max_tokens": 512, "is_truncated": False}
    defaults.update(kwargs)

    completion1 = PromptCompletion(prompt_revision_id=prompt_revision.id, sha256=sha256_1, completion_text=completion_text_1, **defaults)
    completion2 = PromptCompletion(prompt_revision_id=prompt_revision.id, sha256=sha256_2, completion_text=completion_text_2, **defaults)

    temp_dataset.session.add(completion1)
    temp_dataset.session.add(completion2)
    temp_dataset.commit()

    return completion1, completion2


def create_export_template_and_setup(temp_dataset: "DatasetDatabase", facet: Facet, training_type: str, output_format: str,
                                     model_families: list[str], limit_type: str = "percentage", limit_value: int = 100,
                                     order: str = "random", facet_overrides: dict | None = None) -> tuple[ExportTemplate, pathlib.Path]:
    """
    Create an export template with standard configuration.

    This helper eliminates duplicate export template creation code across test files.

    Args:
        temp_dataset: Dataset to create template in
        facet: Facet to use in template
        training_type: Training type (e.g., "DPO", "KTO")
        output_format: Output format (e.g., "JSONL (Anthropic)", "JSONL (TRL)")
        model_families: List of model families
        limit_type: Limit type for facet ("percentage" or "count")
        limit_value: Limit value for facet
        order: Order for facet ("random", "created", etc.)
        facet_overrides: Optional dict of additional facet-specific overrides (e.g., {"max_rating": 6})

    Returns:
        Tuple of (ExportTemplate, pathlib.Path)
    """
    # Build facet configuration
    facet_config = {"facet_id": facet.id, "limit_type": limit_type, "limit_value": limit_value, "order": order}
    if facet_overrides:
        facet_config.update(facet_overrides)

    # Create export template
    template = ExportTemplate.create(temp_dataset, name=f"Test {training_type} Template", description=f"Test {training_type} export",
                                     training_type=training_type, output_format=output_format, model_families=model_families,
                                     facets=[facet_config])
    temp_dataset.commit()

    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    return template, temp_path


def create_sample_with_truncated_completion(temp_dataset: "DatasetDatabase", prompt_text: str = "Test prompt",
                                            sample_title: str = "Test sample", completion_text: str = "Truncated completion",
                                            context_length: int = 2048, max_tokens: int = 128) -> tuple[Sample, PromptCompletion]:
    """
    Create a sample with a truncated completion for beam mode testing.

    This helper eliminates duplicate sample and truncated completion creation code
    that appears in beam mode tests.

    Args:
        temp_dataset: Dataset to create sample in
        prompt_text: Prompt text
        sample_title: Sample title
        completion_text: Completion text
        context_length: Context length
        max_tokens: Max tokens

    Returns:
        Tuple of (sample, completion)
    """
    session = temp_dataset.session
    assert session is not None

    # Create a sample and truncated completion
    prompt_revision = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length, max_tokens)
    sample = Sample.create_if_unique(temp_dataset, sample_title, prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion = create_test_completion(session, prompt_revision, {"is_truncated": True, "completion_text": completion_text})
    session.refresh(completion)

    return sample, completion


def create_sample_with_archived_truncated_completion(temp_dataset: "DatasetDatabase", prompt_text: str = "Test prompt",
                                                     sample_title: str = "Test sample", completion_text: str = "Archived truncated",
                                                     context_length: int = 2048, max_tokens: int = 128) -> tuple[Sample, PromptCompletion]:
    """
    Create a sample with an archived truncated completion for testing.

    This helper eliminates duplicate sample and archived completion creation code.

    Args:
        temp_dataset: Dataset to create sample in
        prompt_text: Prompt text
        sample_title: Sample title
        completion_text: Completion text
        context_length: Context length
        max_tokens: Max tokens

    Returns:
        Tuple of (sample, completion)
    """
    session = temp_dataset.session
    assert session is not None

    # Create a sample and truncated + archived completion
    prompt_revision = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length, max_tokens)
    sample = Sample.create_if_unique(temp_dataset, sample_title, prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion = create_test_completion(session, prompt_revision, {
        "is_truncated": True,
        "is_archived": True,
        "completion_text": completion_text
    })
    session.refresh(completion)

    return sample, completion


def create_facet_pair_and_sample(temp_dataset: "DatasetDatabase", facet1_name: str = "Quality", facet1_desc: str = "Quality facet",
                                 facet2_name: str = "Accuracy", facet2_desc: str = "Accuracy facet", sample_title: str = "Test Sample",
                                 prompt_text: str = "Test prompt", context_length: int = 2048,
                                 max_tokens: int = 512) -> tuple[Facet, Facet, Sample]:
    """
    Create two facets and a sample for facet switch testing.

    This helper eliminates duplicate facet and sample creation code that appears
    in facet switch tests.

    Args:
        temp_dataset: Dataset to create entities in
        facet1_name: Name for first facet
        facet1_desc: Description for first facet
        facet2_name: Name for second facet
        facet2_desc: Description for second facet
        sample_title: Sample title
        prompt_text: Prompt text
        context_length: Context length
        max_tokens: Max tokens

    Returns:
        Tuple of (facet1, facet2, sample)
    """
    facet1 = Facet.create(temp_dataset, facet1_name, facet1_desc)
    facet2 = Facet.create(temp_dataset, facet2_name, facet2_desc)
    temp_dataset.commit()

    # Create sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length, max_tokens)
    sample = Sample.create_if_unique(temp_dataset, sample_title, prompt_revision)
    temp_dataset.commit()

    return facet1, facet2, sample
