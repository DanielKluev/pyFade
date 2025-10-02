"""LLM chat template formatting functions for various model families."""

from py_fade.data_formats.base_data_classes import CommonConversation


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


def get_template_function(model_id: str):
    """
    Get the template function by model ID.
    """
    if "gemma3" in model_id.lower():
        return apply_template_gemma3
    if "qwen3" in model_id.lower():
        return apply_template_qwen3
    return None
