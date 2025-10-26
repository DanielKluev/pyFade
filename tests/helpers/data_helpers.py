"""
Database and data setup helpers for testing.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import TYPE_CHECKING, List, Tuple

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
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
                                       max_tokens: int = 100):
    """
    Create a test PromptCompletion with explicit parameters.

    Eliminates duplicate completion creation code across test files.
    """
    if sha256 is None:
        sha256 = "a" * 64
    completion = PromptCompletion(prompt_revision_id=prompt.id, sha256=sha256, model_id=model_id, temperature=temperature, top_k=top_k,
                                  completion_text=completion_text, context_length=context_length, max_tokens=max_tokens)
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
