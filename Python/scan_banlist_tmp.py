"""Temp script: read messages from live Discord and dump a full word frequency list."""
import asyncio
import os
import re
import unicodedata

import discord
import dotenv

dotenv.load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID_PARADISE = 1416007094339113071

RAW_COUNTS: dict[str, int] = {}
MESSAGE_COUNT = 0
CHANNEL_COUNT = 0
MIN_FREQ = 2  # drop words seen only once


def tokenize(content: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", unicodedata.normalize("NFKC", content))
    return [t.lower() for t in tokens]


async def main() -> None:
    global MESSAGE_COUNT, CHANNEL_COUNT
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        global MESSAGE_COUNT, CHANNEL_COUNT
        print(f"Logged in as {client.user} (id={client.user.id})", flush=True)
        guild = client.get_guild(GUILD_ID_PARADISE)
        if guild is None:
            print("Could not find Paradise guild", flush=True)
            await client.close()
            return

        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=None):
                    if msg.content and not msg.author.bot:
                        for tok in tokenize(msg.content):
                            RAW_COUNTS[tok] = RAW_COUNTS.get(tok, 0) + 1
                        MESSAGE_COUNT += 1
                CHANNEL_COUNT += 1
            except discord.Forbidden:
                continue
            except Exception as e:
                print(f"  channel {channel.name}: {e}", flush=True)

        print(f"Scanned {MESSAGE_COUNT} messages across {CHANNEL_COUNT} channels, "
              f"{len(RAW_COUNTS)} unique words", flush=True)

        ranked = sorted(RAW_COUNTS.items(), key=lambda x: x[1], reverse=True)
        ranked = [item for item in ranked if item[1] >= MIN_FREQ]
        with open("word_freq.txt", "w", encoding="utf-8") as f:
            for tok, cnt in ranked:
                f.write(f"{tok}\t{cnt}\n")
        print(f"Wrote word_freq.txt ({len(ranked)} lines)", flush=True)
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
