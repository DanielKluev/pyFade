"""
Database and data setup helpers for testing.
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, List, Tuple

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.providers.llm_response import LLMResponse, LLMResponseLogprobs

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def ensure_test_facets(dataset: "DatasetDatabase") -> List[Facet]:
    """
    Create standard test facets in the dataset if they don't exist.

    Returns a list of facets that can be used in tests for consistent behavior.
    """
    facet_specs = [
        ("Reasoning", "Logical reasoning and problem-solving capability"),
        ("Creativity", "Creative and imaginative responses"),
        ("Safety", "Safe and appropriate content generation"),
        ("Accuracy", "Factual accuracy and correctness")
    ]

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

    # Handle logprobs conversion from list to LLMResponseLogprobs
    if "logprobs" in overrides and isinstance(overrides["logprobs"], list):
        logprobs_list = overrides["logprobs"]
        overrides["logprobs"] = LLMResponseLogprobs(logprobs_model_id=overrides.get("model_id", defaults["model_id"]),
                                                    logprobs=logprobs_list)

    defaults.update(overrides)
    return LLMResponse(**defaults)


def setup_beam_heatmap_test(dataset: "DatasetDatabase", qt_app) -> Tuple["CompletionFrame", "MockLLMProvider"]:
    """
    Set up a beam mode CompletionFrame with heatmap functionality for testing.
    
    Returns the configured frame and mock provider for further testing.
    """
    # Import here to avoid circular imports
    from py_fade.gui.components.widget_completion import CompletionFrame  # pylint: disable=import-outside-toplevel
    from py_fade.providers.llm_response import SinglePositionTokenLogprobs  # pylint: disable=import-outside-toplevel
    from py_fade.providers.providers_manager import MappedModel  # pylint: disable=import-outside-toplevel
    from py_fade.providers.mock_provider import MockLLMProvider  # pylint: disable=import-outside-toplevel

    beam = create_test_llm_response(completion_text="Hello world",
                                   logprobs=[SinglePositionTokenLogprobs("Hello", -0.1),
                                            SinglePositionTokenLogprobs(" world", -0.8)])
    beam.is_full_response_logprobs = True

    frame = CompletionFrame(dataset, beam, display_mode="beam")

    # Set target model to enable heatmap
    mock_provider = MockLLMProvider()
    test_model = MappedModel("test-beam-model", mock_provider)
    frame.set_target_model(test_model)

    frame.show()
    qt_app.processEvents()

    return frame, mock_provider
