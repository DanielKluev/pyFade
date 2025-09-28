"""
Test ExportTemplate functionality.
"""
import pytest

from py_fade.dataset.export_template import ExportTemplate


class TestExportTemplate:
    """Tests for ExportTemplate class."""

    def test_normalize_output_format_accepts_jsonl_sharegpt(self):
        """Test that _normalize_output_format accepts 'JSONL-ShareGPT' alias."""
        result = ExportTemplate._normalize_output_format("SFT", "JSONL-ShareGPT")
        assert result == "JSONL (ShareGPT)"

        result = ExportTemplate._normalize_output_format("SFT", "jsonl-sharegpt")
        assert result == "JSONL (ShareGPT)"

        result = ExportTemplate._normalize_output_format("SFT", "jsonl sharegpt")
        assert result == "JSONL (ShareGPT)"

    def test_normalize_output_format_existing_formats(self):
        """Test that existing format strings still work."""
        result = ExportTemplate._normalize_output_format("SFT", "JSONL (ShareGPT)")
        assert result == "JSONL (ShareGPT)"

        result = ExportTemplate._normalize_output_format("SFT", "JSON")
        assert result == "JSON"

    def test_normalize_output_format_invalid(self):
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported output format"):
            ExportTemplate._normalize_output_format("SFT", "INVALID_FORMAT")
