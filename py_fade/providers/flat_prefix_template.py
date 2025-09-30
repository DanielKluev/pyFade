"""
Implementation of Zephyr-like flat prefix template for prompt construction,
mainly for internal use and UI.

Uses special tokens to denote system, user, and assistant messages, but no end of turn tokens.
"""

from __future__ import annotations

import re

from py_fade.data_formats.base_data_classes import CommonConversation

FLAT_PREFIX_SYSTEM = "<|system|>"
FLAT_PREFIX_USER = "<|user|>"
FLAT_PREFIX_ASSISTANT = "<|assistant|>"

_TOKEN_TO_ROLE = {
    FLAT_PREFIX_SYSTEM: "system",
    FLAT_PREFIX_USER: "user",
    FLAT_PREFIX_ASSISTANT: "assistant",
}

_TOKEN_PATTERN = re.compile("(" + "|".join(re.escape(token) for token in _TOKEN_TO_ROLE) + ")")


def parse_flat_prefix_string(flat_prefix_string: str | None) -> CommonConversation:
    """
    Parse a flat prefix string into CommonConversation format.

    Args:
        flat_prefix_string (str): The flat prefix string to parse. Role tokens may be
            on separate lines or inline. Whitespace before and after content part is trimmed.
        if `flat_prefix_string` doesn't contain any role tokens, the entire string
            is treated as a single user message.
        if `flat_prefix_string` is empty or None, returns an empty list.

    Returns:
        CommonConversation: A list of messages with 'role' and 'content'.
    """
    if flat_prefix_string is None:
        raise ValueError("flat_prefix_string cannot be None")

    if flat_prefix_string.strip() == "":
        raise ValueError("flat_prefix_string cannot be empty or whitespace")

    messages: CommonConversation = CommonConversation(messages=[])
    current_role: str | None = None
    current_content_parts: list[str] = []
    saw_token = False

    parts = _TOKEN_PATTERN.split(flat_prefix_string)

    for part in parts:
        role = _TOKEN_TO_ROLE.get(part)
        if role is not None:
            saw_token = True
            content = "".join(current_content_parts).strip()
            if current_role is None:
                if content:
                    messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": current_role, "content": content})

            current_role = role
            current_content_parts = []
            continue

        current_content_parts.append(part)

    trailing_content = "".join(current_content_parts).strip()

    if not saw_token:
        if trailing_content:
            messages.append({"role": "user", "content": trailing_content})
        return messages

    if current_role is None:
        if trailing_content:
            messages.append({"role": "user", "content": trailing_content})
    else:
        messages.append({"role": current_role, "content": trailing_content})

    return messages


def apply_flat_prefix_template(messages: list[dict]) -> str:
    """
    Apply the flat prefix template to the given messages.
    """
    prompt = ""
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            prompt += f"{FLAT_PREFIX_SYSTEM} {content}\n"
        elif role == "user":
            prompt += f"{FLAT_PREFIX_USER} {content}\n"
        elif role == "assistant":
            prompt += f"{FLAT_PREFIX_ASSISTANT} {content}\n"
        else:
            prompt += f"{FLAT_PREFIX_USER} {content}\n"  # Default to user role

    return prompt
