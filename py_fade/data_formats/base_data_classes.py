"""
Fundamental language model data classes.
"""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CommonMessage:
    """
    Single message in Message API format.
    Role: "user", "assistant", or "system".
    """
    role: str
    content: str

@dataclass(frozen=True, slots=True)
class CommonConversation:
    """
    Message API conversation format.
    """
    messages: list[CommonMessage]