"""
Test LMEvalResult functionality.
"""
import pytest

from py_fade.data_formats.lm_eval_results import LMEvalResult


class TestLMEvalResult:
    """Tests for LMEvalResult class."""

    def test_save_raises_not_implemented(self):
        """Test that save() method raises NotImplementedError as expected."""
        # Create a mock instance without trying to initialize with real files
        result = object.__new__(LMEvalResult)  # Bypass __init__
        
        with pytest.raises(NotImplementedError, match="read-only and does not support saving"):
            result.save()

        with pytest.raises(NotImplementedError, match="read-only and does not support saving"):
            result.save("/some/path")