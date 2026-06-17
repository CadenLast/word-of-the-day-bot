"""A Discord bot that posts a Word of the Day every morning.

Posts a random common English word (frequency ranks 1000-5000) with its
definition to a configured channel at 10:00 AM America/Chicago, daily.

Set DISCORD_TOKEN and WOTD_CHANNEL_ID in a .env file (see .env.example).
"""

import datetime
import logging
import os
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv

import dictionary
from embed import make_embed, WOTD_CHANNEL_ID
from words import random_word, word_rank

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("DISCORD_TOKEN")

# Post every day at 10:00 AM Chicago time (DST handled automatically).
CHICAGO = ZoneInfo("America/Chicago")
POST_TIME = datetime.time(hour=10, minute=0, tzinfo=CHICAGO)

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# One shared HTTP session for the bot's lifetime.
http_session: aiohttp.ClientSession | None = None


async def fetch_random_definition(
    max_tries: int = 8,
) -> tuple[dictionary.Entry, int | None] | tuple[None, None]:
    """Pick random words until one has a dictionary entry.

    Returns the entry and its usage rank, or (None, None) if none found.
    """
    for _ in range(max_tries):
        word = random_word()
        result = await dictionary.lookup(http_session, word)
        if result is not None:
            return result, word_rank(word)
    return None, None


async def post_word_of_the_day() -> None:
    """Pick a random word and post it to the configured channel."""
    channel = client.get_channel(WOTD_CHANNEL_ID)
    if channel is None:
        logging.warning("WOTD channel %s not found; skipping.", WOTD_CHANNEL_ID)
        return
    entry, rank = await fetch_random_definition()
    if entry is not None:
        await channel.send(embed=make_embed(entry, rank))
        logging.info("Posted Word of the Day: %s (rank %s)", entry.word, rank)


@tasks.loop(time=POST_TIME)
async def word_of_the_day() -> None:
    """Daily scheduled post at 10:00 AM America/Chicago."""
    await post_word_of_the_day()


@word_of_the_day.before_loop
async def before_word_of_the_day() -> None:
    await client.wait_until_ready()


@client.event
async def setup_hook() -> None:
    global http_session
    http_session = dictionary.make_session()
    if WOTD_CHANNEL_ID:
        word_of_the_day.start()
        logging.info("Daily Word of the Day scheduled for 10:00 AM America/Chicago.")
    else:
        logging.warning("WOTD_CHANNEL_ID not set; daily post disabled.")


@client.event
async def on_ready() -> None:
    logging.info("Logged in as %s (id: %s)", client.user, client.user.id)


def main() -> None:
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your token.")
    client.run(TOKEN)


if __name__ == "__main__":
    main()
