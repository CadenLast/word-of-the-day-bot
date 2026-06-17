"""Build and sample from a list of commonly-used English words.

We use `wordfreq`'s frequency-ranked word list and keep only the slice
between two ranks (default ranks 10000-30000). This targets the
"heard it but couldn't quite define it" vocabulary zone -- past the
everyday words but before the obscure ones the dictionary won't have.
"""

import random
import re

from wordfreq import top_n_list

# Only keep plain alphabetic words (drop contractions, numbers, etc.).
_ALPHA = re.compile(r"^[a-z]+$")

START_RANK = 50000
END_RANK = 75000

# Full frequency-ranked list up to END_RANK, most common first. Built once
# at import time and reused for both sampling and rank lookups.
_RANKED = top_n_list("en", END_RANK)
# 1-based usage rank for each word: rank 1 is the single most common word.
_RANK = {word: i + 1 for i, word in enumerate(_RANKED)}


def build_word_pool(start_rank: int = START_RANK, end_rank: int = END_RANK) -> list[str]:
    """Return common English words ranked between start_rank and end_rank."""
    sliced = _RANKED[start_rank - 1 : end_rank]
    return [w for w in sliced if _ALPHA.match(w) and len(w) > 2]


# Build once at import time so we don't recompute on every call.
WORD_POOL = build_word_pool()


def random_word() -> str:
    """Pick a random word from the common-word pool."""
    return random.choice(WORD_POOL)


def word_rank(word: str) -> int | None:
    """Return the 1-based usage rank of a word, or None if unranked."""
    return _RANK.get(word)
