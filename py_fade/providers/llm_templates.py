"""LLM chat template formatting functions for various model families."""

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage


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


def apply_template_qwen3(messages: list[dict]) -> str:
    """
    Apply the Qwen3 chat template to the given messages.
    """
    prompt = ""
    # prompt = "<bos>\n"
    user = messages.pop(0)
    prompt += f"<|im_start|>user\n{user['content']}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    if messages:
        assistant = messages.pop(0)
        prompt += f"{assistant['content']}"

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
