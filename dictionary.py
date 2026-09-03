"""Thin async client for the Free Dictionary API (dictionaryapi.dev).

No API key required. If you later want Merriam-Webster, you only need to
swap out `lookup()` to call their endpoint with your key and map the
response into the same `Entry` shape.
"""

import asyncio
import ssl
from dataclasses import dataclass

import aiohttp
import certifi

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2


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
    """Look up a word, returning all meanings. None if no entry (HTTP 404).

    Retries a few times on transient failures (server 5xx errors, timeouts,
    dropped connections) before giving up, so a brief upstream hiccup doesn't
    propagate up and stall the whole scheduled post. The dictionary API can
    take 30+ seconds to respond on a cache miss, so each attempt gets a
    generous timeout rather than failing fast.
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
            if d.get("definition")
        ]
        if senses:
            meanings.append(Meaning(meaning.get("partOfSpeech", ""), senses))

    if not meanings:
        return None
    return Entry(word=entry.get("word", word), phonetic=phonetic, meanings=meanings)
