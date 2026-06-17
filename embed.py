"""Shared embed builder and channel config used by both bot.py and word."""

import os
from urllib.parse import quote

import discord
from dotenv import load_dotenv

import dictionary

load_dotenv()

WOTD_CHANNEL_ID = int(os.environ.get("WOTD_CHANNEL_ID", "0"))

FIELD_LIMIT = 1024
DICTIONARY_URL = "https://www.merriam-webster.com/dictionary/{word}"


def make_embed(entry: dictionary.Entry, rank: int | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"\U0001f4d6 Word of the Day: {entry.word.capitalize()}",
        url=DICTIONARY_URL.format(word=quote(entry.word)),
        color=discord.Color.blurple(),
    )

    subtitle = []
    if entry.phonetic:
        subtitle.append(entry.phonetic)
    if rank is not None:
        subtitle.append(f"usage rank #{rank:,}")
    if subtitle:
        embed.description = " · ".join(subtitle)

    for meaning in entry.meanings:
        lines = []
        for i, sense in enumerate(meaning.senses, 1):
            line = f"{i}. {sense.definition}"
            if sense.example:
                line += f"\n   _{sense.example}_"
            lines.append(line)
        value = "\n".join(lines)
        if len(value) > FIELD_LIMIT:
            value = value[: FIELD_LIMIT - 1].rstrip() + "…"
        embed.add_field(name=meaning.part_of_speech or "—", value=value, inline=False)
    return embed
