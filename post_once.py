"""One-off: post today's Word of the Day immediately, bypassing the 10:00 AM
schedule. Safe to run any time -- doesn't touch or reschedule the daily loop
that lives in bot.py; that keeps running on its normal schedule regardless.
"""

import asyncio

import discord

import bot as botmodule
import dictionary


async def main() -> None:
    if not botmodule.TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set.")

    client = discord.Client(intents=discord.Intents.default())
    botmodule.client = client

    @client.event
    async def on_ready() -> None:
        try:
            botmodule.http_session = dictionary.make_session()
            await botmodule.post_word_of_the_day()
        finally:
            await botmodule.http_session.close()
            await client.close()

    await client.start(botmodule.TOKEN)


asyncio.run(main())
