"""LLM chat template formatting functions for various model families."""

import re
from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage


def merge_system_and_user(messages: CommonConversation) -> CommonConversation:
    """
    Merge system message into the first user message if present.
    """
    raw_messages = messages.messages.copy()
    if len(raw_messages) >= 2 and raw_messages[0].role == "system" and raw_messages[1].role == "user":
        system_msg = raw_messages.pop(0)
        user_msg = raw_messages.pop(0)
        merged_user_msg = CommonMessage(role="user", content=system_msg.content + "\n" + user_msg.content)
        return CommonConversation(messages=[merged_user_msg] + raw_messages)
    return messages


def apply_template_gemma3(messages: CommonConversation) -> str:
    """
    Apply the Gemma3 chat template to the given messages.

    Gemma3 expects "<bos>\n" at the start, but llama-cpp internally adds it, so we skip adding it here.
    Gemma3 uses only 'user' and 'model' roles, system role is treated as user.
    Each turn looks like this:
        <start_of_turn>{role}\n{content}<end_of_turn>\n
    """
    prompt = ""
    continue_previous = False
    for i, message in enumerate(messages.messages):
        role = message.role
        content = message.content
        if role == "assistant":
            role = "model"
        if i == 0:
            if role == "system":  # Gemma 3 doesn't have system role, it is part of user
                role = "user"
                continue_previous = True
            prompt += f"<start_of_turn>{role}\n{content}"
        elif continue_previous:
            prompt += f"\n{content}"
            continue_previous = False
        else:
            prompt += f"<end_of_turn>\n<start_of_turn>{role}\n{content}"
    if messages.messages and messages.messages[-1].role == "user":  # If last message is user, start model turn
        prompt += "<end_of_turn>\n<start_of_turn>model\n"
    return prompt


def apply_template_qwen3(messages: CommonConversation) -> str:
    """
    Apply the Qwen3 chat template to the given messages.

    Roles: 'system', 'user', 'assistant'
    Each turn looks like this:
        <|im_start|>{role}\n{content}<|im_end|>\n

    Qwen3 doesn't use <bos> token at all. Results in annoying off-by-one errors in llama.cpp.
    """
    prompt = ""
    previous_role = None
    for i, message in enumerate(messages.messages):
        role = message.role
        content = message.content
        if role not in ("system", "user", "assistant"):
            raise ValueError(f"Unsupported role '{role}' for Qwen3 template.")
        if previous_role is not None and previous_role in (role, 'system'):
            raise ValueError("Consecutive messages with the same role or system role in between are not allowed.")
        if i == len(messages.messages) - 1 and role == "assistant":  # Last message is assistant, no end tag
            prompt += f"<|im_start|>{role}\n{content}"
        else:
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    if messages.messages and messages.messages[-1].role == "user":  # If last message is user, start assistant turn
        prompt += "<|im_start|>assistant\n"

    return prompt


def apply_template_llama3(messages: CommonConversation) -> str:
    """
    Apply the Llama3 chat template to the given messages.

    Roles: 'system', 'user', 'assistant'
    Each turn looks like this:
        <|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>

    BOS token: <|begin_of_text|>
    """
    prompt = ""
    previous_role = None
    for i, message in enumerate(messages.messages):
        role = message.role
        content = message.content
        if role not in ("system", "user", "assistant"):
            raise ValueError(f"Unsupported role '{role}' for Llama3 template.")
        if previous_role is not None and previous_role in (role, 'system'):
            raise ValueError("Consecutive messages with the same role or system role in between are not allowed.")
        if i == len(messages.messages) - 1 and role == "assistant":  # Last message is assistant, no end tag
            prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}"
        else:
            prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
    if messages.messages and messages.messages[-1].role == "user":  # If last message is user, start assistant turn
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

    return prompt


def apply_template_mistral(messages: CommonConversation) -> str:
    """
    Apply the Mistral chat template to the given messages.

    Mistral uses only 'user' and 'assistant' roles, system role is treated as user.
    Each turn looks like this:
        user: [INST] {content} [/INST]
        assistant: {content}</s>
    """
    messages = merge_system_and_user(messages)
    prompt = ""
    for i, message in enumerate(messages.messages):
        role = message.role
        content = message.content
        if role not in ("user", "assistant"):
            raise ValueError(f"Unsupported role '{role}' for Mistral template.")
        if role == "user":
            prompt += f"[INST] {content} [/INST] "
        elif i == len(messages.messages) - 1:
            prompt += f"{content}"
        else:
            prompt += f"{content}</s>"
    return prompt.strip()


def merged_plaintext(messages: CommonConversation) -> str:
    """
    Merge all messages into plain text without special formatting.
    """
    prompt = ""
    for message in messages.messages:
        prompt += message.content + "\n"
    return prompt.strip()


def get_template_function(model_id: str):
    """
    Get the template function by model ID.
    """
    if "gemma3" in model_id.lower():
        return apply_template_gemma3
    if "qwen3" in model_id.lower():
        return apply_template_qwen3
    if "mistral" in model_id.lower():
        return apply_template_mistral
    if "llama3" in model_id.lower():
        return apply_template_llama3
    return None


def strip_template_gemma3(templated_text: str) -> str:
    """
    Strip Gemma3 chat template tokens from templated text, returning plain content.

    Removes:
    - <bos> token at the beginning
    - <start_of_turn>user/model markers
    - <end_of_turn> markers
    - Leading/trailing whitespace

    Args:
        templated_text: Text with Gemma3 template tokens

    Returns:
        Plain text content without template tokens
    """
    # Remove <bos> token
    text = templated_text.replace("<bos>", "")
    # Remove <start_of_turn>user and <start_of_turn>model
    text = re.sub(r"<start_of_turn>(?:user|model)\n?", "", text)
    # Remove <end_of_turn>
    text = text.replace("<end_of_turn>", "")
    # Clean up excess whitespace but preserve paragraph structure
    text = text.strip()
    return text


def strip_template_qwen3(templated_text: str) -> str:
    """
    Strip Qwen3 chat template tokens from templated text, returning plain content.

    Removes:
    - <|im_start|>role markers
    - <|im_end|> markers
    - Leading/trailing whitespace

    Args:
        templated_text: Text with Qwen3 template tokens

    Returns:
        Plain text content without template tokens
    """
    # Remove <|im_start|>role markers (system, user, assistant)
    text = re.sub(r"<\|im_start\|>(?:system|user|assistant)\n?", "", templated_text)
    # Remove <|im_end|> markers
    text = text.replace("<|im_end|>", "")
    # Clean up excess whitespace
    text = text.strip()
    return text


def strip_template_llama3(templated_text: str) -> str:
    """
    Strip Llama3 chat template tokens from templated text, returning plain content.

    Removes:
    - <|begin_of_text|> token
    - <|start_header_id|>role<|end_header_id|> markers
    - <|eot_id|> markers
    - Leading/trailing whitespace

    Args:
        templated_text: Text with Llama3 template tokens

    Returns:
        Plain text content without template tokens
    """
    # Remove <|begin_of_text|> token
    text = templated_text.replace("<|begin_of_text|>", "")
    # Remove header markers like <|start_header_id|>system<|end_header_id|>
    text = re.sub(r"<\|start_header_id\|>(?:system|user|assistant)<\|end_header_id\|>\n*", "", text)
    # Remove <|eot_id|> markers
    text = text.replace("<|eot_id|>", "")
    # Clean up excess whitespace
    text = text.strip()
    return text


def strip_template_mistral(templated_text: str) -> str:
    """
    Strip Mistral chat template tokens from templated text, returning plain content.

    Removes:
    - [INST] and [/INST] markers
    - </s> end-of-sequence markers
    - Leading/trailing whitespace

    Args:
        templated_text: Text with Mistral template tokens

    Returns:
        Plain text content without template tokens
    """
    # Remove [INST] and [/INST] markers
    text = templated_text.replace("[INST]", "").replace("[/INST]", "")
    # Remove </s> markers
    text = text.replace("</s>", "")
    # Clean up excess whitespace
    text = text.strip()
    return text


def strip_chat_template(templated_text: str, model_id: str = "") -> str:
    """
    Automatically detect and strip chat template tokens from templated text.

    Tries to detect the template type from the model_id or from markers in the text,
    then applies the appropriate stripping function.

    Args:
        templated_text: Text potentially containing chat template tokens
        model_id: Optional model identifier to help detect template type

    Returns:
        Plain text content without template tokens
    """
    # Try to detect from model_id first
    if model_id:
        model_lower = model_id.lower()
        if "gemma" in model_lower:
            return strip_template_gemma3(templated_text)
        if "qwen" in model_lower:
            return strip_template_qwen3(templated_text)
        if "llama" in model_lower:
            return strip_template_llama3(templated_text)
        if "mistral" in model_lower:
            return strip_template_mistral(templated_text)

    # Fall back to detecting from content markers
    # Check for template-specific markers and apply the corresponding stripper
    template_markers = [
        (("<start_of_turn>", "<bos>"), strip_template_gemma3),
        (("<|im_start|>", "<|im_end|>"), strip_template_qwen3),
        (("<|begin_of_text|>", "<|start_header_id|>"), strip_template_llama3),
        (("[INST]", "[/INST]"), strip_template_mistral),
    ]

    for markers, stripper_func in template_markers:
        if any(marker in templated_text for marker in markers):
            return stripper_func(templated_text)

    # No template detected, return as-is
    return templated_text.strip()
