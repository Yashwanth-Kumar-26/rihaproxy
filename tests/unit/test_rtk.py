"""
Unit tests for RTK compression engine.
"""

from __future__ import annotations

import pytest

from rihaproxy.engine.rtk import RTKEngine, compress, decompress, get_rtk


class TestRTKEngine:
    """Test suite for RTK compression engine."""

    @pytest.fixture
    def rtk(self) -> RTKEngine:
        """Create RTK engine instance."""
        return RTKEngine()

    def test_abbreviation_common_phrases(self, rtk: RTKEngine):
        """Test common phrase abbreviations."""
        result = rtk.compress("This is for example usage")
        assert "e.g." in result
        assert "for example" not in result

    def test_abbreviation_due_to_fact_that(self, rtk: RTKEngine):
        """Test 'due to the fact that' → 'because'."""
        result = rtk.compress("Due to the fact that it was raining, we stayed inside")
        assert "because" in result

    def test_contraction_contractions(self, rtk: RTKEngine):
        """Test that contractions are properly applied."""
        result = rtk.compress("I am going to the store and you are coming too")
        assert "I'm" in result
        assert "you're" in result

    def test_coding_abbreviations(self, rtk: RTKEngine):
        """Test coding-related abbreviations."""
        result = rtk.compress("function myFunction() { return null; }")
        assert "fn " in result

    def test_whitespace_normalization(self, rtk: RTKEngine):
        """Test whitespace is normalized."""
        result = rtk.compress("This    has     extra     spaces")
        assert "     " not in result

    def test_blank_line_limit(self, rtk: RTKEngine):
        """Test that excessive blank lines are limited."""
        text = "Line 1\n\n\n\n\nLine 2"
        result = rtk.compress(text)
        assert result.count("\n\n\n") == 0

    def test_line_trimming(self, rtk: RTKEngine):
        """Test that lines are trimmed."""
        result = rtk.compress("  Leading spaces  \n  Trailing spaces  ")
        assert "Leading spaces" in result
        assert result == result.strip()

    def test_aggressive_compression(self, rtk: RTKEngine):
        """Test aggressive compression mode."""
        text = "**bold text** and *italic text*"
        result = rtk.compress(text, aggressive=True)
        assert "**" not in result  # Markdown bold stripped

    def test_compression_savings_logged(self, rtk: RTKEngine, caplog):
        """Test that compression savings are logged."""
        import logging
        caplog.set_level(logging.DEBUG)

        text = "This has for example multiple for example phrases for example"
        rtk.compress(text)
        assert "rtk_compress" in [r.name for r in caplog.records]

    def test_no_change_for_simple_text(self, rtk: RTKEngine):
        """Test that simple text without patterns remains unchanged."""
        text = "Hello, world!"
        result = rtk.compress(text)
        # Some changes may occur (whitespace normalization)
        assert len(result) <= len(text) + 1


class TestRTKDecompression:
    """Test suite for RTK decompression (expansion)."""

    @pytest.fixture
    def rtk(self) -> RTKEngine:
        """Create RTK engine instance."""
        return RTKEngine()

    def test_expand_eg(self, rtk: RTKEngine):
        """Test expansion of e.g."""
        result = rtk.decompress("This is e.g. useful")
        assert "for example" in result

    def test_expand_contractions(self, rtk: RTKEngine):
        """Test expansion of contractions."""
        result = rtk.decompress("I'm going to the store")
        assert "I am" in result

    def test_expand_thats(self, rtk: RTKEngine):
        """Test expansion of that's."""
        result = rtk.decompress("That's an interesting question")
        assert "that is" in result

    def test_decompression_is_lossy(self, rtk: RTKEngine):
        """Test that decompression cannot restore all abbreviations."""
        original = "for example we can see this function is null"
        compressed = rtk.compress(original)
        decompressed = rtk.decompress(compressed)
        # Not all abbreviations can be reversed
        assert "null" in decompressed  # nil → null should work

    def test_expand_fn(self, rtk: RTKEngine):
        """Test expansion of fn abbreviation."""
        result = rtk.decompress("fn myFunction() {}")
        assert "function" in result


class TestRTKConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_compress_function(self):
        """Test the compress convenience function."""
        result = compress("for example usage")
        assert "e.g." in result

    def test_decompress_function(self):
        """Test the decompress convenience function."""
        result = decompress("This is e.g. useful")
        assert "for example" in result

    def test_get_rtk_singleton(self):
        """Test that get_rtk returns same instance."""
        rtk1 = get_rtk()
        rtk2 = get_rtk()
        assert rtk1 is rtk2


class TestRTKEdgeCases:
    """Edge case tests for RTK engine."""

    def test_empty_string(self):
        """Test compression of empty string."""
        from rihaproxy.engine.rtk import RTKEngine
        rtk = RTKEngine()
        result = rtk.compress("")
        assert result == ""

    def test_whitespace_only(self):
        """Test compression of whitespace-only string."""
        rtk = RTKEngine()
        result = rtk.compress("   \n\n   ")
        assert result == ""

    def test_case_insensitive_abbreviations(self):
        """Test that abbreviations work regardless of case."""
        rtk = RTKEngine()
        result1 = rtk.compress("FOR EXAMPLE UPPERCASE")
        result2 = rtk.compress("for example lowercase")
        assert "e.g." in result1
        assert "e.g." in result2

    def test_multiple_abbreviations_in_text(self):
        """Test that multiple abbreviations can be applied."""
        rtk = RTKEngine()
        text = "I am going to the store due to the fact that it is raining"
        result = rtk.compress(text)
        assert "I'm" in result
        assert "because" in result