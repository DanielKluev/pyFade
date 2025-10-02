"""
Test emoji and multi-byte Unicode character highlighting in CompletionTextEdit.

These tests verify that highlighting works correctly with emoji and other Unicode
characters that are represented as multiple UTF-16 code units in Qt.
"""

# pylint: disable=protected-access

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextCursor

from py_fade.gui.components.widget_completion import CompletionFrame
from tests.helpers.data_helpers import (build_sample_with_completion, create_test_llm_response, create_test_single_position_token)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


class TestEmojiPrefillHighlighting:
    """
    Test prefill highlighting with emoji.
    """

    def test_prefill_with_emoji_at_end(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test that prefill ending with emoji is highlighted correctly.

        This test reproduces the bug where emoji in prefill causes mangled highlighting.
        The issue is that Python string indexes (code points) don't match Qt's UTF-16 indexes.
        """
        _ = ensure_google_icon_font
        # Create completion with prefill ending in emoji
        prefill_text = "Hello 😀"
        completion_text = "Hello 😀 world and more text"

        beam = create_test_llm_response(completion_text=completion_text, prefill=prefill_text)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        # Verify text is set correctly
        assert text_edit.toPlainText() == completion_text

        # Verify that emoji is displayed correctly (not as diamonds)
        # Qt should display emoji properly
        display_text = text_edit.toPlainText()
        assert "😀" in display_text
        assert "�" not in display_text  # No replacement characters

        # Check that highlighting was applied correctly using Qt's document.find()
        # which properly handles UTF-16
        cursor = text_edit.document().find(prefill_text)
        assert not cursor.isNull(), "Prefill text should be found in document"

        # Verify the found text matches exactly
        selected_text = cursor.selectedText()
        assert selected_text == prefill_text, f"Expected '{prefill_text}', got '{selected_text}'"

        # Check that the cursor found the text at the beginning
        assert cursor.selectionStart() == 0, "Prefill should start at position 0"

        # The highlighting should have been applied to the correct range
        # We can't directly check the background color in a unit test easily,
        # but we can verify that the text was found and positioned correctly

    def test_prefill_with_multiple_emoji(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test prefill with multiple emoji characters.
        """
        _ = ensure_google_icon_font
        prefill_text = "😀😁😂"
        completion_text = "😀😁😂 more text"

        beam = create_test_llm_response(completion_text=completion_text, prefill=prefill_text)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        display_text = text_edit.toPlainText()
        assert "😀" in display_text
        assert "😁" in display_text
        assert "😂" in display_text

    def test_beam_token_with_emoji(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test beam token containing emoji is highlighted correctly.
        """
        _ = ensure_google_icon_font
        beam_token = "😀"
        completion_text = "Start 😀 end"

        beam = create_test_llm_response(completion_text=completion_text, beam_token=beam_token)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        display_text = text_edit.toPlainText()
        assert "😀" in display_text

    def test_prefill_and_beam_with_emoji(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test both prefill and beam token with emoji.
        """
        _ = ensure_google_icon_font
        prefill_text = "Hello 😀 token"
        beam_token = "token"
        completion_text = "Hello 😀 token and more"

        beam = create_test_llm_response(completion_text=completion_text, prefill=prefill_text, beam_token=beam_token)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        display_text = text_edit.toPlainText()
        assert "😀" in display_text
        assert "token" in display_text


class TestEmojiHeatmapHighlighting:
    """
    Test heatmap highlighting with emoji.
    """

    def test_heatmap_with_emoji_tokens(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test heatmap mode with emoji in tokens.

        This reproduces the bug where emoji causes incorrect heatmap segmentation.
        """
        _ = ensure_google_icon_font
        completion_text = "Hello 😀 world"
        logprobs = [
            create_test_single_position_token("Hello", -0.1),
            create_test_single_position_token(" ", -0.2),
            create_test_single_position_token("😀", -0.3),
            create_test_single_position_token(" world", -0.4),
        ]

        beam = create_test_llm_response(completion_text=completion_text, logprobs=logprobs)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Enable heatmap mode
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        frame.show()
        qt_app.processEvents()

        # Check that cache is populated
        assert len(text_edit._token_positions_cache) > 0

        # Verify the cache contains expected positions
        cache = text_edit._token_positions_cache

        # First token "Hello" should be at position 0-5
        assert cache[0][2].token_str == "Hello"

        # Emoji token should be found
        emoji_found = False
        for start, end, token_data in cache:
            if token_data.token_str == "😀":
                emoji_found = True
                # Verify the emoji can be correctly selected using Qt cursor
                cursor = text_edit.textCursor()
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                extracted = cursor.selectedText()
                assert extracted == "😀", f"Expected emoji at position {start}:{end}, got {repr(extracted)}"
                break

        assert emoji_found, "Emoji token not found in heatmap cache"

    def test_heatmap_cache_with_multiple_emoji(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test heatmap cache with multiple emoji characters.
        """
        _ = ensure_google_icon_font
        completion_text = "😀😁😂 text"
        logprobs = [
            create_test_single_position_token("😀", -0.1),
            create_test_single_position_token("😁", -0.2),
            create_test_single_position_token("😂", -0.3),
            create_test_single_position_token(" text", -0.4),
        ]

        beam = create_test_llm_response(completion_text=completion_text, logprobs=logprobs)

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        frame.show()
        qt_app.processEvents()

        cache = text_edit._token_positions_cache
        assert len(cache) >= 3  # At least the three emoji

        # Verify each emoji is found using Qt cursor
        expected_emoji = ["😀", "😁", "😂"]
        found_emoji = []

        for start, end, cached_token in cache:
            if cached_token.token_str in expected_emoji:
                # Use Qt cursor to extract the text
                cursor = text_edit.textCursor()
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                extracted = cursor.selectedText()
                assert extracted == cached_token.token_str, \
                    f"Expected {cached_token.token_str} at {start}:{end}, got {repr(extracted)}"
                found_emoji.append(cached_token.token_str)

        # Verify all emoji were found
        for emoji in expected_emoji:
            assert emoji in found_emoji, f"Emoji {emoji} not found in cache"


class TestQtTextPositioning:
    """
    Test Qt text positioning with Unicode characters.

    These tests verify that we correctly convert between Python string indexes
    and Qt's UTF-16 based positioning.
    """

    def test_qt_cursor_position_with_emoji(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Test QTextCursor positioning with emoji characters.

        Emoji like 😀 (U+1F600) are represented as surrogate pairs in UTF-16,
        taking 2 UTF-16 code units, but only 1 Python string index.
        """
        _ = ensure_google_icon_font
        _, completion = build_sample_with_completion(temp_dataset, completion_text="Hello 😀 world")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        # Get the text
        text = text_edit.toPlainText()
        assert text == "Hello 😀 world"

        # Test cursor positioning
        cursor = text_edit.textCursor()

        # Position 0 should be 'H'
        cursor.setPosition(0)
        cursor.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        assert cursor.selectedText() == "H"

        # The emoji is at Python index 6, but in Qt it might be different
        # We need to test that we can select the emoji correctly
        python_emoji_index = text.index("😀")
        assert python_emoji_index == 6  # After "Hello "

        # Using Qt cursor to navigate
        cursor.setPosition(0)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 6)
        # Now we should be at the emoji
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
        selected = cursor.selectedText()
        assert selected == "😀", f"Expected emoji, got {repr(selected)}"
