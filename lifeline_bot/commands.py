"""
Lifeline's recognized vocabulary, plus the logic that scans a chat message
for matches.

This used to live inline inside the GUI's `_on_chat_message` handler. Pulling
it out into `CommandMatcher` makes the matching algorithm independently
testable (no Tkinter, no threads) and reusable outside the GUI.
"""

import re

# ── Single-word commands ──────────────────────────────────────────────────
# These are the words/phrases Rio recognizes in the PS2 game.
LIFELINE_COMMANDS = {
    # Movement
    "go", "move", "walk", "run", "follow", "come", "here", "back",
    "left", "right", "forward", "ahead", "behind", "north", "south", "east", "west",
    "up", "down", "stop", "wait", "stay", "return", "approach", "enter", "exit",
    # Connectives / prepositions (needed for sentences like "go to the table")
    "to", "the", "a", "an", "and", "then", "next", "after",
    "in", "into", "on", "onto", "over", "under", "through",
    "with", "without", "at", "from", "toward", "towards",
    # Actions
    "get", "take", "grab", "pick", "drop", "use", "open", "close", "push", "pull",
    "hit", "attack", "fight", "kick", "dodge", "hide", "crouch", "stand",
    "look", "examine", "search", "check", "read",
    "give", "throw", "put", "place", "carry", "hold", "release",
    "eat", "drink", "heal", "rest", "sleep", "wake",
    "climb", "jump", "duck", "turn",
    "shoot", "fire", "reload", "aim", "flee", "recover",
    "unlock", "lock", "break", "destroy", "press", "flip",
    # Communication
    "yes", "no", "okay", "ok", "help", "call", "talk", "say", "speak", "answer",
    "thanks", "sorry", "please", "hurry", "careful",
    # Items / context
    "door", "key", "gun", "weapon", "item", "box", "chest", "table",
    "light", "switch", "button", "stairs", "ladder", "window", "wall", "floor",
    "room", "hall", "hallway",
    "knife", "bat", "stick", "bottle", "can", "food", "water",
    "medicine", "bandage", "first", "aid",
    "phone", "radio", "computer", "panel", "machine",
    "bag", "backpack", "cabinet", "drawer", "shelf",
    # Positional / directional
    "there", "that", "this", "front", "side", "corner", "end",
    # Status
    "status", "health", "ammo", "inventory", "map", "where", "what", "how",
    # System
    "save", "cancel", "skip", "repeat", "again",
    # Single-word official keywords from the FAQ
    "consultation", "strafe", "taunt", "jump", "jumpback", "dodge",
    "approach", "flee", "shoot", "reload", "recover", "front", "back",
    "suicide", "walk", "run", "stop", "check",
    # Words extracted from official phrases (auto-generated)
    "about", "alien", "alive", "allen", "am", "announcer", "any", "are",
    "around", "attacked", "auto", "away", "bark", "by", "camera", "captain",
    "category", "cell", "clothes", "coming", "conducting", "cranky", "dead", "detaining",
    "did", "do", "dog", "earlier", "earth", "fake", "far", "for",
    "friends", "fuck", "game", "gino", "girl", "got", "gravity", "great",
    "green", "group", "happened", "hate", "have", "helen", "his", "hotel",
    "humanoid", "i", "if", "is", "isn", "it", "johnson", "joseph",
    "jsl", "kill", "lady", "leave", "like", "ll", "looking", "love",
    "low", "m", "made", "man", "manager", "me", "microphone", "monster",
    "monsters", "naomi", "now", "number", "of", "off", "orb", "paracelsus",
    "people", "philosopher", "pm", "poor", "pose", "power", "powers", "re",
    "reflexes", "relationship", "remnants", "rescue", "research", "researching", "restaurant", "s",
    "safe", "sells", "sex", "sexy", "she", "should", "sign", "sit",
    "so", "spin", "stone", "strong", "structure", "sucks", "t", "tanaka",
    "team", "tell", "they", "things", "think", "time", "ve", "was",
    "wasn", "we", "were", "when", "who", "why", "will", "wonder",
    "words", "you", "your", "yourself", "zero", "zoom",
}

# Multi-word phrases the game officially recognises (from FAQ keyword list).
# These are matched as complete units from chat messages — a phrase match
# takes priority over individual word matching.
LIFELINE_PHRASES = {
    # Normal keywords
    "go back",
    # Scenario keywords
    "why were you in the detaining cell",
    "where am i",
    "who's naomi",
    "what is jsl",
    "what are you looking for",
    "what was that monster",
    "who is helen johnson",
    "why are you so cranky",
    "i wonder if naomi's alive",
    "what is the manager like",
    "what do you think of the pm",
    "do you have any friends",
    "what's the relationship with gino",
    "is a rescue team coming",
    "how are things on earth",
    "naomi isn't around",
    "what are they researching here",
    "what do you think of allen",
    "where is the announcer",
    "tell me about yourself",
    "tell me what you're looking for",
    "powers and alien",
    "what do you think of powers",
    "how far away are you",
    "naomi wasn't there",
    "about this hotel's structure",
    "humanoid alien",
    "i wonder if the pm and his people are ok",
    "what do you think of that captain",
    "that alien earlier",
    "you've got great reflexes",
    "i wonder if naomi is safe",
    "you're looking for a green orb",
    "i wonder if the manager is ok",
    "where is gino",
    "the announcer was dead",
    "that man in the restaurant",
    "when we get to earth",
    "how was earth",
    "is this hotel ok",
    "why did tanaka turn into a monster",
    "the poor manager",
    "what happened to powers",
    "i wonder if gino is ok",
    "what is paracelsus",
    "the remnants of paracelsus",
    "the power of words",
    "are you close to me now",
    "is it zero gravity",
    "what's a philosopher's stone",
    "the first lady was attacked by an alien",
    "that allen",
    "what happened to gino",
    "what was that group",
    "where is naomi",
    "the monsters were made here",
    "allen was conducting research here",
    "you're strong",
    "it's about naomi",
    "what's a fake stone",
    "powers is joseph",
    "what should we do",
    # Special keywords
    "microphone check",
    "zoom in",
    "low kick",
    "category game",
    "spin the gun",
    "sexy pose",
    "auto-fire",
    "she sells",
    "break time",
    "i'll leave it to you",
    "camera check",
    # Battle keywords
    "number 1", "number 2", "number 3",
    "turn right", "turn left",
    # Fun keywords
    "kill yourself",
    "i love you",
    "i hate you",
    "bark like a dog",
    "fuck you",
    "what's your sign",
    "i'm sorry",
    "sit down",
    "will you have sex with me",
    "are you a girl",
    "this game sucks",
    "take off your clothes",
}

# Only letters, digits, apostrophes and spaces survive normalization.
_NORMALIZE_RE = re.compile(r"[^a-z0-9' ]")
_WORD_RE = re.compile(r"[a-z]+")


def normalize_message(message: str) -> str:
    """Lowercase a chat message and strip everything but letters/digits/'/space."""
    return _NORMALIZE_RE.sub(" ", message.strip().lower())


class CommandMatcher:
    """
    Scans a chat message for recognized commands using two-pass matching:

      Pass 1 — scan for known multi-word phrases (longest phrase first, so
               "go back" wins over a lone "back" at the same position).
      Pass 2 — scan the remaining, unclaimed text for individual command
               words.

    Matches are returned in the order they appeared in the message, with
    duplicates preserved (e.g. "hello hello hello" -> 3 matches) — spam
    control is a separate, caller-side concern (cooldowns).
    """

    def __init__(self, commands: set, phrases: set):
        self.commands = set(commands)
        self.phrases = set(phrases)

    def find_matches(self, message: str) -> list:
        """Return an ordered list of matched words/phrases for `message`."""
        normalized = normalize_message(message)
        phrase_matches, claimed_spans = self._match_phrases(normalized)
        word_matches = self._match_words(normalized, claimed_spans)

        all_matches = phrase_matches + word_matches
        all_matches.sort(key=lambda position_and_text: position_and_text[0])
        return [text for _position, text in all_matches]

    def _match_phrases(self, normalized_text: str):
        """Find every non-overlapping phrase match, longest phrases first."""
        matches = []
        claimed_spans = []
        for phrase in sorted(self.phrases, key=len, reverse=True):
            pattern = re.compile(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])")
            search_from = 0
            while True:
                found = pattern.search(normalized_text, search_from)
                if not found:
                    break
                start, end = found.start(), found.end()
                if not self._overlaps_any(start, end, claimed_spans):
                    claimed_spans.append((start, end))
                    matches.append((start, phrase))
                search_from = end
        return matches, claimed_spans

    def _match_words(self, normalized_text: str, claimed_spans):
        """Find individual command words outside any already-claimed span."""
        matches = []
        for found in _WORD_RE.finditer(normalized_text):
            if self._inside_any(found.start(), found.end(), claimed_spans):
                continue
            word = found.group()
            if word in self.commands:
                matches.append((found.start(), word))
        return matches

    @staticmethod
    def _overlaps_any(start, end, spans):
        return any(start < s_end and end > s_start for s_start, s_end in spans)

    @staticmethod
    def _inside_any(start, end, spans):
        return any(start >= s_start and end <= s_end for s_start, s_end in spans)
