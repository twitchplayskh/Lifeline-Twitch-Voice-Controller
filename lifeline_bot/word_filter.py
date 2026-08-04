"""Two-layer profanity / hate-word screening for text headed to TTS."""

try:
    from better_profanity import profanity as _profanity_checker

    _profanity_checker.load_censor_words()
    HAS_PROFANITY_LIBRARY = True
except Exception:  # noqa: BLE001 - missing package or failed word-list load
    HAS_PROFANITY_LIBRARY = False

# Words that must never reach TTS, even if the profanity library is missing
# or a variant slips past it. Kept as plain fragments rather than annotated
# for the reason each is blocked.
_HARD_BLOCKED_WORDS = {
    "nigger", "nigga", "faggot", "fag", "kike", "spic", "chink",
    "cunt", "fuck", "shit", "bitch", "asshole", "bastard", "whore",
    "slut", "piss", "cock", "dick", "pussy", "retard", "tranny",
    "dyke", "wetback", "gook", "cracker", "honky",
}


class WordFilter:
    """
    Screens individual words before they're spoken aloud.

    Note: this only runs on words that already passed the Lifeline command
    whitelist, so it's a safety net rather than a general chat filter.
    """

    def is_clean(self, word: str) -> bool:
        normalized = word.lower().strip()
        if normalized in _HARD_BLOCKED_WORDS:
            return False
        if HAS_PROFANITY_LIBRARY and _profanity_checker.contains_profanity(normalized):
            return False
        return True
