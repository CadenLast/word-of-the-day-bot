"""Thin async client for Datamuse, with a dictionaryapi.dev fallback for
words Datamuse doesn't have.

No API key required for either source.
"""

import asyncio
import re
import ssl
from dataclasses import dataclass

import aiohttp
import certifi

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
DATAMUSE_URL = "https://api.datamuse.com/words"
MAX_RETRIES = 1
RETRY_DELAY_SECONDS = 2

_DATAMUSE_POS_NAMES = {"n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb"}

# Both sources pull raw Wiktionary entries, which mix in senses like "An
# English surname originating as an occupation", "Acronym of National
# Aeronautics and Space Administration", or "A river in Douglas County,
# Oregon" alongside the common-word senses we actually want. Drop those
# rather than the whole word, since a word like "smith" has a perfectly good
# common-noun sense too.
_PLACE_NOUN = (
    r"ghost town|unincorporated community|community|township|county|borough"
    r"|parish|province|country|village|town|city|hamlet|river|lake|creek"
    r"|stream|mountain|island|bay"
)
_EXCLUDED_SENSE_RE = re.compile(
    r"^(?:(?:a|an)\s+(?:\w+\s+){0,3}surname\b"
    r"|surname\s+of\b"
    r"|(?:acronym|initialism|abbreviation)\s+of\b"
    r"|alternative letter-case form of\b"
    r"|(?:a|an)\s+(?:\w+\s+){0,3}given name\b"
    r"|(?:a|an)\s+(?:\w+\s+){0,3}(?:" + _PLACE_NOUN + r")\b.*\b(?:in|of)\b"
    r"|(?:several|a number of)\s+(?:\w+\s+){0,2}"
    r"(?:places|rivers?|townships?|villages?|towns?|counties|communities|lakes?|mountains?|islands?)\b)",
    re.IGNORECASE,
)
# Named institutions (e.g. "Smith College") are identified by a capitalized
# proper name in the source text, so this one must stay case-sensitive --
# matching it case-insensitively would also exclude ordinary lowercase
# definitions that merely mention "a college in ...".
_NAMED_INSTITUTION_RE = re.compile(
    r"^[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,3}\s+(?:College|University|Township)\b"
)


def _is_excluded_sense(definition: str) -> bool:
    """True if a definition marks the word as a surname, given name, place
    name, named institution, or abbreviation rather than a common word."""
    definition = definition.strip()
    return bool(_EXCLUDED_SENSE_RE.match(definition)) or bool(_NAMED_INSTITUTION_RE.match(definition))


def make_session() -> aiohttp.ClientSession:
    """Create a ClientSession with a proper CA bundle.

    Uses certifi so HTTPS works even when the system Python is missing its
    root certificates (a common macOS Python.framework issue).
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ctx)
    return aiohttp.ClientSession(connector=connector)


@dataclass
class Sense:
    definition: str
    example: str | None = None


@dataclass
class Meaning:
    part_of_speech: str
    senses: list[Sense]


@dataclass
class Entry:
    word: str
    phonetic: str | None
    meanings: list[Meaning]


async def lookup(session: aiohttp.ClientSession, word: str) -> Entry | None:
    """Look up a word, returning all meanings, or None if no entry exists.

    Tries Datamuse first (dictionaryapi.dev has been prone to extended
    outages on cache-miss words), falling back to dictionaryapi.dev if
    Datamuse is unavailable or doesn't have an entry.
    """
    try:
        entry = await _lookup_datamuse(session, word)
    except (aiohttp.ClientError, TimeoutError):
        entry = None
    if entry is not None:
        return entry
    try:
        return await _lookup_primary(session, word)
    except (aiohttp.ClientError, TimeoutError):
        return None


async def _lookup_primary(session: aiohttp.ClientSession, word: str) -> Entry | None:
    """Look up a word via dictionaryapi.dev. None if no entry (HTTP 404).

    Retries a few times on transient failures (server 5xx errors, timeouts,
    dropped connections) before giving up. The dictionary API can take 30+
    seconds to respond on a cache miss, so each attempt gets a generous
    timeout rather than failing fast.
    """
    for attempt in range(MAX_RETRIES):
        is_last_attempt = attempt == MAX_RETRIES - 1
        try:
            async with session.get(API_URL.format(word=word), timeout=60) as resp:
                if resp.status == 404:
                    return None
                if resp.status >= 500 and not is_last_attempt:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError):
            if is_last_attempt:
                raise
            await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
            continue
        break

    # The API returns a list of entries; grab the first usable one.
    entry = data[0]

    phonetic = entry.get("phonetic")
    if not phonetic:  # fall back to the first pronunciation that has text
        for p in entry.get("phonetics", []):
            if p.get("text"):
                phonetic = p["text"]
                break

    meanings: list[Meaning] = []
    for meaning in entry.get("meanings", []):
        senses = [
            Sense(d["definition"], d.get("example"))
            for d in meaning.get("definitions", [])
            if d.get("definition") and not _is_excluded_sense(d["definition"])
        ]
        if senses:
            meanings.append(Meaning(meaning.get("partOfSpeech", ""), senses))

    if not meanings:
        return None
    return Entry(word=entry.get("word", word), phonetic=phonetic, meanings=meanings)


async def _lookup_datamuse(session: aiohttp.ClientSession, word: str) -> Entry | None:
    """Look up a word via Datamuse. None if it has no definitions.

    Datamuse has no phonetics and coarser definitions than dictionaryapi.dev
    (and pulls raw Wiktionary entries, including surnames/place names), but
    it's been far more reliable than dictionaryapi.dev for cache-miss words.
    """
    async with session.get(
        DATAMUSE_URL, params={"sp": word, "md": "d", "max": 1}, timeout=15
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    if not data or data[0].get("word") != word or not data[0].get("defs"):
        return None

    meanings_by_pos: dict[str, list[Sense]] = {}
    for raw in data[0]["defs"]:
        pos, _, definition = raw.partition("\t")
        definition = definition.strip()
        if _is_excluded_sense(definition):
            continue
        pos_name = _DATAMUSE_POS_NAMES.get(pos, pos)
        meanings_by_pos.setdefault(pos_name, []).append(Sense(definition))

    meanings = [Meaning(pos, senses) for pos, senses in meanings_by_pos.items() if senses]
    if not meanings:
        return None
    return Entry(word=word, phonetic=None, meanings=meanings)
