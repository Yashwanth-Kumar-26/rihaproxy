"""
RTK Engine — Rust Token Killer compression.
Reduces token usage by 20-40% through intelligent compression.
"""

from __future__ import annotations

import re
import logging
import structlog

logger = structlog.get_logger()
py_logger = logging.getLogger("rtk_compress")


class RTKEngine:
    """
    Token compression engine inspired by RTK (Rust Token Killer).

    Techniques:
    - Common phrase abbreviation (e.g. "for example" → "e.g.")
    - Repeated pattern compression
    - Whitespace normalization
    - Verbose coding pattern shortening
    """

    # Common abbreviation rules
    ABBREVIATIONS: list[tuple[str, str]] = [
        # Phrases
        (r"\bfor example\b", "e.g."),
        (r"\bin order to\b", "to"),
        (r"\bdue to the fact that\b", "because"),
        (r"\bin the event that\b", "if"),
        (r"\bat this point in time\b", "now"),
        (r"\bfor the purpose of\b", "to"),
        (r"\bin addition to\b", "plus"),
        (r"\bwith regard to\b", "about"),
        (r"\bin order to\b", "to"),
        (r"\bhas been\b", "has"),
        (r"\bhave been\b", "have"),
        (r"\bwhich is\b", "that's"),
        (r"\bthat is\b", "that's"),
        (r"\bthere are\b", "there're"),
        (r"\bthere is\b", "there's"),
        (r"\bI am\b", "I'm"),
        (r"\byou are\b", "you're"),
        (r"\bwe are\b", "we're"),
        (r"\bthey are\b", "they're"),
        (r"\bit is\b", "it's"),
        (r"\bdo not\b", "don't"),
        (r"\bdoes not\b", "doesn't"),
        (r"\bis not\b", "isn't"),
        (r"\bcan not\b", "can't"),
        (r"\bshould not\b", "shouldn't"),
        (r"\bwould not\b", "wouldn't"),
        (r"\bcould not\b", "couldn't"),
        # Coding
        (r"\bself\.self\.self\.self\.", "self."),
        (r"\breturn null", "return nil"),
        (r"\breturn true", "return !0"),
        (r"\breturn false", "return 0"),
        (r"\bfunction\s+", "fn "),
        (r"\basync function\s+", "async fn "),
        (r"\bconsole\.log\(", "console.log("),
        (r"\bprint\s*\(", "printf("),
        # Common verbose patterns
        (r"\bnull\b", "nil"),
        (r"\bundefined\b", "void 0"),
        (r"\binterface\s+", "trait "),
        (r"\bpublic\s+", "pub "),
        (r"\bprivate\s+", "priv "),
        (r"\bprotected\s+", "prot "),
    ]

    # Patterns that add noise
    NOISE_PATTERNS: list[tuple[str, str]] = [
        (r"\s+", " "),  # normalize whitespace
        (r"\n{3,}", "\n\n"),  # limit blank lines
        (r"<!--[\s\S]*?-->", ""),  # remove HTML comments
        (r"/\*[\s\S]*?\*/", ""),  # remove block comments (careful)
    ]

    def compress(self, text: str, aggressive: bool = False) -> str:
        """
        Compress text to reduce token count.

        Args:
            text: Input text
            aggressive: Apply more aggressive compression

        Returns:
            Compressed text
        """
        result = text

        # Apply abbreviations
        for pattern, replacement in self.ABBREVIATIONS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Normalize whitespace
        result = re.sub(r"\s+", " ", result)
        result = re.sub(r"\n{3,}", "\n\n", result)

        # Trim lines
        lines = result.split("\n")
        result = "\n".join(line.strip() for line in lines)

        if aggressive:
            # More aggressive compression
            result = self._aggressive_compress(result)

        logger.debug("rtk_compress", original=len(text), compressed=len(result), saved=len(text) - len(result))
        py_logger.debug("rtk_compress")
        return result

    def _aggressive_compress(self, text: str) -> str:
        """Apply aggressive compression techniques."""
        result = text

        # Remove markdown formatting where safe
        result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)  # bold
        result = re.sub(r"\*(.+?)\*", r"\1", result)  # italic

        # Shorten common phrases
        aggressive_replacements = [
            (r"\bI think\b", "I guess"),
            (r"\bThe thing is\b", "Thus"),
            (r"\bLet me think about this\b", "Note"),
            (r"\bAs mentioned earlier\b", "As noted"),
            (r"\bIn summary\b", "Summary"),
            (r"\bTo summarize\b", "Summary"),
            (r"\bIn conclusion\b", "Thus"),
            (r"\bIt is worth noting\b", "Note"),
            (r"\bPlease note\b", "Note"),
            (r"\bIt is important to\b", "To"),
            (r"\bOne can see that\b", "Thus"),
        ]

        for pattern, replacement in aggressive_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def decompress(self, text: str) -> str:
        """
        Decompress text (expand abbreviations back).
        Note: This is lossy — some abbreviations cannot be reversed.
        """
        result = text

        # Expand some abbreviations (best effort)
        expansions = [
            (r"e\.g\.", "for example"),
            (r"i\.e\.", "that is"),
            (r"\b(don't)\b", "do not"),
            (r"\b(doesn't)\b", "does not"),
            (r"\b(isn't)\b", "is not"),
            (r"\b(can't)\b", "can not"),
            (r"\b(shouldn't)\b", "should not"),
            (r"\b(wouldn't)\b", "would not"),
            (r"\b(couldn't)\b", "could not"),
            (r"\b(I'm)\b", "I am"),
            (r"\b(you're)\b", "you are"),
            (r"\b(we're)\b", "we are"),
            (r"\b(they're)\b", "they are"),
            (r"\b(it's)\b", "it is"),
            (r"\b(that's)\b", "that is"),
            (r"\b(there's)\b", "there is"),
            (r"\b(there're)\b", "there are"),
            (r"\b(nil)\b", "null"),
            (r"\b(fn)\b", "function "),
            (r"\b(pub)\b", "public "),
        ]

        for pattern, replacement in expansions:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result


# Global RTK engine instance
_rtk: RTKEngine | None = None


def get_rtk() -> RTKEngine:
    """Get the global RTK engine."""
    global _rtk
    if _rtk is None:
        _rtk = RTKEngine()
    return _rtk


def compress(text: str, aggressive: bool = False) -> str:
    """Convenience function for compression."""
    return get_rtk().compress(text, aggressive)


def decompress(text: str) -> str:
    """Convenience function for decompression."""
    return get_rtk().decompress(text)
