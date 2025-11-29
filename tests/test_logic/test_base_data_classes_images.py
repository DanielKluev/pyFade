"""
Test suite for base data classes with image support.

Tests core functionality of CommonMessage and CommonConversation with images:
- MessageImage creation and serialization
- CommonMessage with optional images
- CommonConversation with images in messages
- Equality comparisons with images

Edge cases covered:
- Messages without images (backward compatibility)
- Messages with multiple images
- Conversation has_images detection
"""
from __future__ import annotations

import pathlib

import pytest

from py_fade.data_formats.base_data_classes import (
    CommonConversation,
    CommonMessage,
    MessageImage,
)


class TestMessageImage:
    """
    Tests for MessageImage dataclass.
    """

    def test_create_from_file_path(self, tmp_path: pathlib.Path) -> None:
        """
        Test creating MessageImage from file path.

        Verifies that filename is correctly extracted from path.
        """
        test_image = tmp_path / "test_image.png"
        test_image.touch()

        msg_image = MessageImage.from_file_path(str(test_image))

        assert msg_image.file_path == str(test_image)
        assert msg_image.filename == "test_image.png"

    def test_create_from_nested_path(self, tmp_path: pathlib.Path) -> None:
        """
        Test creating MessageImage from nested file path.

        Verifies that nested paths are handled correctly.
        """
        subdir = tmp_path / "images" / "nested"
        subdir.mkdir(parents=True)
        test_image = subdir / "photo.jpg"
        test_image.touch()

        msg_image = MessageImage.from_file_path(str(test_image))

        assert test_image.name in msg_image.file_path
        assert msg_image.filename == "photo.jpg"

    def test_as_dict(self, tmp_path: pathlib.Path) -> None:
        """
        Test MessageImage serialization to dict.

        Verifies as_dict returns correct structure.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        msg_image = MessageImage.from_file_path(str(test_image))
        result = msg_image.as_dict()

        assert result["file_path"] == str(test_image)
        assert result["filename"] == "test.png"

    def test_file_exists(self, tmp_path: pathlib.Path) -> None:
        """
        Test file_exists correctly reports file existence.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        msg_image = MessageImage.from_file_path(str(test_image))
        assert msg_image.file_exists() is True

        test_image.unlink()
        assert msg_image.file_exists() is False


class TestCommonMessageWithImages:
    """
    Tests for CommonMessage with image support.
    """

    def test_message_without_images(self) -> None:
        """
        Test creating message without images (backward compatibility).

        Verifies that messages work as before without images.
        """
        msg = CommonMessage(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.images == ()
        assert msg.has_images() is False

    def test_message_with_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test creating message with images.

        Verifies that images can be attached to messages.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        image = MessageImage.from_file_path(str(test_image))
        msg = CommonMessage(role="user", content="Look at this image", images=(image,))

        assert msg.role == "user"
        assert msg.content == "Look at this image"
        assert len(msg.images) == 1
        assert msg.images[0].filename == "test.png"
        assert msg.has_images() is True

    def test_message_with_multiple_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test creating message with multiple images.

        Verifies that multiple images can be attached.
        """
        images = []
        for i in range(3):
            img = tmp_path / f"image{i}.png"
            img.touch()
            images.append(MessageImage.from_file_path(str(img)))

        msg = CommonMessage(role="user", content="Multiple images", images=tuple(images))

        assert len(msg.images) == 3

    def test_message_as_dict_without_images(self) -> None:
        """
        Test as_dict without images for backward compatibility.

        Verifies that messages without images serialize without 'images' key.
        """
        msg = CommonMessage(role="user", content="Hello")
        result = msg.as_dict()

        assert result["role"] == "user"
        assert result["content"] == "Hello"
        assert "images" not in result

    def test_message_as_dict_with_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test as_dict with images includes images in output.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        msg = CommonMessage(role="user", content="Image attached", images=(image,))
        result = msg.as_dict()

        assert result["role"] == "user"
        assert result["content"] == "Image attached"
        assert "images" in result
        assert len(result["images"]) == 1
        assert result["images"][0]["filename"] == "test.png"

    def test_message_equality_without_images(self) -> None:
        """
        Test equality comparison without images.

        Verifies backward compatibility with dict comparison.
        """
        msg = CommonMessage(role="user", content="Hello")

        # Equal to another CommonMessage
        assert msg == CommonMessage(role="user", content="Hello")

        # Equal to dict
        assert msg == {"role": "user", "content": "Hello"}

        # Not equal if content differs
        assert msg != CommonMessage(role="user", content="World")

    def test_message_equality_with_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test equality comparison with images.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        msg1 = CommonMessage(role="user", content="Hello", images=(image,))
        msg2 = CommonMessage(role="user", content="Hello", images=(image,))
        msg3 = CommonMessage(role="user", content="Hello")

        assert msg1 == msg2
        assert msg1 != msg3  # Different because msg3 has no images


class TestCommonConversationWithImages:
    """
    Tests for CommonConversation with image support.
    """

    def test_from_single_user_without_images(self) -> None:
        """
        Test creating conversation from single user message without images.

        Verifies backward compatibility.
        """
        conv = CommonConversation.from_single_user("Hello")

        assert len(conv.messages) == 1
        assert conv.messages[0].role == "user"
        assert conv.messages[0].content == "Hello"
        assert conv.messages[0].has_images() is False
        assert conv.has_images() is False

    def test_from_single_user_with_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test creating conversation from single user message with images.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        conv = CommonConversation.from_single_user("Look at this", images=(image,))

        assert len(conv.messages) == 1
        assert conv.messages[0].content == "Look at this"
        assert conv.messages[0].has_images() is True
        assert conv.has_images() is True

    def test_append_message_with_images_from_dict(self, tmp_path: pathlib.Path) -> None:
        """
        Test appending message with images from dict.

        Verifies that dict with images can be appended.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        conv = CommonConversation(messages=[CommonMessage(role="system", content="Be helpful")])
        conv.append({"role": "user", "content": "See this image", "images": [{"file_path": str(test_image), "filename": "test.png"}]})

        assert len(conv.messages) == 2
        assert conv.messages[1].has_images() is True
        assert conv.has_images() is True

    def test_conversation_has_images_multiple_messages(self, tmp_path: pathlib.Path) -> None:
        """
        Test has_images detects images in any message.

        Verifies that has_images returns True if any message has images.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        # Conversation with no images
        conv1 = CommonConversation(messages=[
            CommonMessage(role="user", content="Hello"),
            CommonMessage(role="assistant", content="Hi there"),
        ])
        assert conv1.has_images() is False

        # Conversation with image in first message
        conv2 = CommonConversation(messages=[
            CommonMessage(role="user", content="Look", images=(image,)),
            CommonMessage(role="assistant", content="I see"),
        ])
        assert conv2.has_images() is True

    def test_as_list_with_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test as_list serialization includes images.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        conv = CommonConversation(messages=[
            CommonMessage(role="user", content="Image here", images=(image,)),
        ])

        result = conv.as_list()

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Image here"
        assert "images" in result[0]
        assert result[0]["images"][0]["filename"] == "test.png"

    def test_copy_with_prefill_preserves_images(self, tmp_path: pathlib.Path) -> None:
        """
        Test copy_with_prefill preserves images in original messages.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()
        image = MessageImage.from_file_path(str(test_image))

        conv = CommonConversation(messages=[
            CommonMessage(role="user", content="Describe this", images=(image,)),
        ])

        new_conv = conv.copy_with_prefill("The image shows")

        assert len(new_conv.messages) == 2
        assert new_conv.messages[0].has_images() is True
        assert new_conv.messages[1].role == "assistant"
        assert new_conv.messages[1].content == "The image shows"
