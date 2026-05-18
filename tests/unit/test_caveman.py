"""
Unit tests for Caveman mode compression.
"""

from __future__ import annotations

import pytest

from rihaproxy.engine.caveman import CavemanMode, compress, get_caveman


class TestCavemanMode:
    """Test suite for Caveman mode compression."""

    @pytest.fixture
    def caveman(self) -> CavemanMode:
        """Create Caveman mode instance."""
        return CavemanMode()

    def test_strip_preface_sure(self, caveman: CavemanMode):
        """Test stripping 'Sure' preface."""
        result = caveman.compress("Sure, I'd be happy to help!")
        assert "Sure" not in result

    def test_strip_preface_certainly(self, caveman: CavemanMode):
        """Test stripping 'Certainly' preface."""
        result = caveman.compress("Certainly! Here's the answer:")
        assert "Certainly" not in result

    def test_strip_preface_of_course(self, caveman: CavemanMode):
        """Test stripping 'Of course' preface."""
        result = caveman.compress("Of course, let me explain")
        assert "Of course" not in result

    def test_strip_preface_let_me(self, caveman: CavemanMode):
        """Test stripping 'Let me' preface."""
        result = caveman.compress("Let me think about this...")
        assert "Let me" not in result

    def test_strip_preface_thank_you(self, caveman: CavemanMode):
        """Test stripping 'Thank you' preface."""
        result = caveman.compress("Thank you for your question.\n\nHere's the answer")
        assert "Thank you" not in result

    def test_markdown_bold_stripping_level2(self, caveman: CavemanMode):
        """Test markdown bold stripping at level 2."""
        text = "This is **bold** and this is *italic*"
        result = caveman.compress(text, level=2)
        assert "**" not in result
        assert "This is bold" in result

    def test_markdown_headers_stripping_level2(self, caveman: CavemanMode):
        """Test markdown headers stripping at level 2."""
        text = "# Header 1\n## Header 2\n### Header 3\nNormal text"
        result = caveman.compress(text, level=2)
        assert "#" not in result.split("\n")[0]  # First line should not have #
        assert "Header 1" in result

    def test_bullet_points_normalized_level2(self, caveman: CavemanMode):
        """Test bullet points are normalized at level 2."""
        text = "- Item 1\n- Item 2\n- Item 3"
        result = caveman.compress(text, level=2)
        assert "- " in result

    def test_numbered_lists_normalized_level2(self, caveman: CavemanMode):
        """Test numbered lists are normalized at level 2."""
        text = "1. First\n2. Second\n3. Third"
        result = caveman.compress(text, level=2)
        # Numbers should be converted to dashes
        assert "- " in result

    def test_verbose_phrases_trimmed_level2(self, caveman: CavemanMode):
        """Test verbose phrases are trimmed at level 2."""
        text = "Please note that this is important"
        result = caveman.compress(text, level=2)
        assert "please note that" not in result
        # The core message should remain after trimming the verbose phrase
        assert "this is important" in result

    def test_level1_preserves_markdown(self, caveman: CavemanMode):
        """Test that level 1 preserves markdown."""
        text = "This is **bold** text"
        result = caveman.compress(text, level=1)
        assert "**bold**" in result

    def test_level3_aggressive_compression(self, caveman: CavemanMode):
        """Test level 3 aggressive compression."""
        text = "This\n\n\n\n\nis\n\n\n\n\na\n\n\n\ntest"
        result = caveman.compress(text, level=3)
        assert "\n\n\n\n" not in result  # Multiple newlines collapsed
        assert "  " not in result  # Multiple spaces collapsed

    def test_code_comments_trimmed_aggressive(self, caveman: CavemanMode):
        """Test code comments are trimmed in aggressive mode."""
        text = "//  TODO: fix this\n//  NOTE: important"
        result = caveman.compress(text, level=3)
        assert "//  TODO:" not in result
        assert "//TODO:" in result

    def test_whitespace_normalization(self, caveman: CavemanMode):
        """Test that whitespace is normalized."""
        result = caveman.compress("Word1    word2\n\n\n\n\nWord3")
        assert "    " not in result

    def test_compression_savings_logged(self, caveman: CavemanMode, caplog):
        """Test that compression savings are logged."""
        import logging
        caplog.set_level(logging.DEBUG)

        text = "Sure, here's a very verbose explanation that goes on and on and on"
        caveman.compress(text, level=2)
        assert "caveman_compress" in [r.name for r in caplog.records]


class TestCavemanConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_compress_function(self):
        """Test the compress convenience function."""
        result = compress("Sure, here's the answer")
        assert "Sure" not in result

    def test_compress_with_level(self):
        """Test the compress function with level parameter."""
        text = "This is **bold** text"
        result = compress(text, level=2)
        assert "**" not in result

    def test_get_caveman_singleton(self):
        """Test that get_caveman returns same instance."""
        c1 = get_caveman()
        c2 = get_caveman()
        assert c1 is c2


class TestCavemanEdgeCases:
    """Edge case tests for Caveman mode."""

    def test_empty_string(self):
        """Test compression of empty string."""
        caveman = CavemanMode()
        result = caveman.compress("")
        assert result == ""

    def test_whitespace_only(self):
        """Test compression of whitespace-only string."""
        caveman = CavemanMode()
        result = caveman.compress("   \n\n   ")
        # After normalization, should be minimal
        assert result.strip() == ""

    def test_code_block_preservation(self):
        """Test that code blocks are preserved."""
        caveman = CavemanMode()
        code = """Here is some code:
```
def hello():
    print("Hello")
```
End of code."""
        result = caveman.compress(code, level=2)
        assert "```" in result

    def test_case_insensitive_preface_stripping(self):
        """Test that preface stripping is case-insensitive."""
        caveman = CavemanMode()
        result1 = caveman.compress("SURE, here's the answer")
        result2 = caveman.compress("sure, here's the answer")
        assert "SURE" not in result1
        assert "sure" not in result2

    def test_multiple_preface_patterns(self):
        """Test that multiple preface patterns are stripped."""
        caveman = CavemanMode()
        text = "Of course, certainly, I'm happy to help"
        result = caveman.compress(text)
        assert "Of course" not in result
        assert "Certainly" not in result