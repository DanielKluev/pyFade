from __future__ import annotations

import pytest

from py_fade.providers.flat_prefix_template import (
    FLAT_PREFIX_ASSISTANT,
    FLAT_PREFIX_SYSTEM,
    FLAT_PREFIX_USER,
    parse_flat_prefix_string,
)


def test_parse_none_returns_empty():
    assert parse_flat_prefix_string(None) == []


def test_parse_blank_returns_empty():
    assert parse_flat_prefix_string("\n\t  ") == []


def test_parse_without_tokens_defaults_to_user():
    content = "Hello\nWorld"
    assert parse_flat_prefix_string(content) == [{"role": "user", "content": content}]


def test_parse_inline_tokens_trims_content():
    flat_prefix = (
        f"{FLAT_PREFIX_SYSTEM} System prompt  "
        f"{FLAT_PREFIX_USER}\nUser question\n"
        f"{FLAT_PREFIX_ASSISTANT}Assistant reply"
    )

    messages = parse_flat_prefix_string(flat_prefix)

    assert messages == [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User question"},
        {"role": "assistant", "content": "Assistant reply"},
    ]


def test_parse_multi_line_tokens():
    flat_prefix = (
        f"{FLAT_PREFIX_SYSTEM}\nYou are helpful.\n\n"
        f"{FLAT_PREFIX_USER}\n Answer politely. \n"
        f"{FLAT_PREFIX_ASSISTANT}\nSure thing! \n"
    )

    messages = parse_flat_prefix_string(flat_prefix)

    assert messages == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Answer politely."},
        {"role": "assistant", "content": "Sure thing!"},
    ]


def test_parse_leading_text_before_first_token():
    flat_prefix = "Lead in text\n" f"{FLAT_PREFIX_ASSISTANT}Response"

    messages = parse_flat_prefix_string(flat_prefix)

    assert messages == [
        {"role": "user", "content": "Lead in text"},
        {"role": "assistant", "content": "Response"},
    ]


def test_parse_consecutive_tokens_preserves_empty_message():
    flat_prefix = (
        f"{FLAT_PREFIX_USER}" f"{FLAT_PREFIX_ASSISTANT}Response" f"{FLAT_PREFIX_SYSTEM}"
    )

    messages = parse_flat_prefix_string(flat_prefix)

    assert messages == [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Response"},
        {"role": "system", "content": ""},
    ]
