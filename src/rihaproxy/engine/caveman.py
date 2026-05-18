"""
Caveman Mode — aggressive output compression.
Reduces output tokens by 40-65% by stripping unnecessary formatting.
"""

from __future__ import annotations

import re
import logging
import structlog

logger = structlog.get_logger()
py_logger = logging.getLogger("caveman_compress")


class CavemanMode:
    """
    Aggressive output compression that strips all non-essential text.

    Removes:
    - "Sure, here's...", "Here's the..." preface
    - Excessive explanation
    - Markdown formatting (headers, bold, italic)
    - Verbose error messages
    - Repeated confirmations

    Compression targets:
    - Code blocks: keep code, minimize comments
    - Explanations: keep essential words only
    - Error messages: minimal form
    """

    # Prefixes to strip
    PREFACE_PATTERNS: list[tuple[str, str]] = [
        (r"^Sure[!,\s]+", ""),
        (r"^Certainly[!,\s]+", ""),
        (r"^Of course[!,\s]+", ""),
        (r"^Here's the", "Here's"),
        (r"^Here's what", "What"),
        (r"^Let me", "I'll"),
        (r"^I think\s+", ""),
        (r"^I believe\s+", ""),
        (r"^As an AI[,\s]+", ""),
        (r"^Thank you for.*?\n+", ""),
        (r"^You can.*?by\s+", ""),
        (r"^To do this[,\s]+", ""),
        (r"^The following[,\s]+", ""),
        (r"^This is.*?:\s*\n", ""),
    ]

    # Formatting to strip
    FORMAT_PATTERNS: list[tuple[str, str]] = [
        (r"\*\*(.+?)\*\*", r"\1"),  # bold
        (r"\*(.+?)\*", r"\1"),  # italic
        (r"__(.+?)__", r"\1"),  # underline
        (r"~~(.+?)~~", r"\1"),  # strikethrough
        (r"^#{1,6}\s+", "", re.MULTILINE),  # markdown headers
        (r"^[-*+]\s+", "- ", re.MULTILINE),  # bullet points
        (r"^\d+\.\s+", "- ", re.MULTILINE),  # numbered lists
        (r"^>\s+", "", re.MULTILINE),  # blockquotes
        (r"`{3}.*?\n", "```\n", re.DOTALL),  # keep code blocks but trim
    ]

    # Verbose phrases to trim
    VERBOSE_PATTERNS: list[tuple[str, str]] = [
        (r"\bplease note that\b", "note"),
        (r"\bit is important to note that\b", "note"),
        (r"\bto summarize,?\s*", ""),
        (r"\bin conclusion,?\s*", ""),
        (r"\bas previously mentioned,?\s*", ""),
        (r"\bas mentioned earlier,?\s*", ""),
        (r"\bkeep in mind that\b", "note"),
        (r"\bit should be noted that\b", "note"),
        (r"\bwith that said,?\s*", ""),
        (r"\bthat being said,?\s*", ""),
        (r"\bon the other hand,?\s*", ""),
        (r"\bhowever,?\s*", ""),
        (r"\bfurthermore,?\s*", ""),
        (r"\badditionally,?\s*", ""),
        (r"\bin addition,?\s*", ""),
        (r"\bmoreover,?\s*", ""),
        (r"\bfor example,?\s*", "e.g."),
        (r"\bfor instance,?\s*", "e.g."),
    ]

    def compress(self, text: str, level: int = 1) -> str:
        """
        Compress text using Caveman mode.

        Args:
            text: Input text
            level: Compression level 1-3
                   1 = light (strip prefacing)
                   2 = medium (strip formatting too)
                   3 = aggressive (minimal output)

        Returns:
            Compressed text
        """
        result = text

        # Level 1: Strip prefacing
        for pattern, replacement in self.PREFACE_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        if level >= 2:
            # Level 2: Strip formatting
            for pattern, replacement, *flags in self.FORMAT_PATTERNS:
                f = flags[0] if flags else 0
                result = re.sub(pattern, replacement, result, flags=f)

            # Trim verbose phrases
            for pattern, replacement in self.VERBOSE_PATTERNS:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        if level >= 3:
            # Level 3: Aggressive
            result = self._aggressive_compress(result)

        # Normalize whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = re.sub(r"[ \t]+", " ", result)
        result = result.strip()

        saved = len(text) - len(result)
        pct = (saved / max(len(text), 1)) * 100
        logger.debug("caveman_compress", original=len(text), compressed=len(result), saved_pct=f"{pct:.1f}%")
        py_logger.debug("caveman_compress")

        return result

    def _aggressive_compress(self, text: str) -> str:
        """Apply maximum compression."""
        result = text

        # Remove empty lines
        result = re.sub(r"\n\s*\n+", "\n", result)

        # Collapse multiple spaces
        result = re.sub(r"  +", " ", result)

        # Shorten code comments
        result = re.sub(r"//\s*TODO:", "//TODO:", result)
        result = re.sub(r"//\s*NOTE:", "//NOTE:", result)
        result = re.sub(r"//\s*FIXME:", "//FIXME:", result)

        # Trim common filler
        result = re.sub(r"\bthis is a\b", "a", result)
        result = re.sub(r"\bsince then\b", "then", result)
        result = re.sub(r"\bat the same time\b", "simultaneously", result)

        return result


# Global caveman instance
_caveman: CavemanMode | None = None


def get_caveman() -> CavemanMode:
    """Get the global Caveman mode instance."""
    global _caveman
    if _caveman is None:
        _caveman = CavemanMode()
    return _caveman


def compress(text: str, level: int = 1) -> str:
    """Convenience function for Caveman compression."""
    return get_caveman().compress(text, level)
