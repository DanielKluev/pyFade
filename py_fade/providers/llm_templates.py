def apply_template_gemma3(messages: list[dict]) -> str:
    """
    Apply the Gemma3 chat template to the given messages.
    """
    prompt = ""
    # prompt = "<bos>\n"
    user = messages.pop(0)
    prompt += f"<start_of_turn>user\n{user['content']}<end_of_turn>\n"
    prompt += "<start_of_turn>model\n"
    if messages:
        assistant = messages.pop(0)
        prompt += f"{assistant['content']}"

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
