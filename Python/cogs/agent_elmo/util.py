import re

import discord


def split_message_for_discord(message: str) -> list[str]:
    """Splits a message into chunks of max 1900 chars, preserving code blocks and spoilers."""
    pattern = re.compile(r"(```[\s\S]*?```|`[^`\n]+`|\|\|[\s\S]+?\|\|)")

    partial = ""
    complete_chunks = []

    for part in pattern.split(message):
        if not part:
            continue

        if len(partial) + len(part) <= 1900:
            partial = partial + part
            continue

        if len(partial) > 0:
            complete_chunks.append(partial)
            partial = ""

        # Handle the part (might be a code block or regular text)
        if part.startswith("```"):
            opener, closer = "```", "```"
            # Strip existing delimiters to avoid duplication
            content = part[3:-3]
            while len(content) > 1900:
                chunk = content[:1900]
                complete_chunks.append(f"{opener}{chunk}{closer}")
                content = content[1900:]
            partial = f"{opener}{content}{closer}"
        elif part.startswith("`"):
            opener, closer = "`", "`"
            content = part[1:-1]
            while len(content) > 1900:
                chunk = content[:1900]
                complete_chunks.append(f"{opener}{chunk}{closer}")
                content = content[1900:]
            partial = f"{opener}{content}{closer}"
        elif part.startswith("||"):
            opener, closer = "||", "||"
            content = part[2:-2]
            while len(content) > 1900:
                chunk = content[:1900]
                complete_chunks.append(f"{opener}{chunk}{closer}")
                content = content[1900:]
            partial = f"{opener}{content}{closer}"
        else:
            # Regular text
            while len(part) > 1900:
                chunk = part[:1900]
                complete_chunks.append(chunk)
                part = part[1900:]
            partial = part

    if len(partial) > 0:
        complete_chunks.append(partial)

    return complete_chunks


async def easy_send(channel: discord.abc.Messageable, message: str) -> None:
    """Splits a message and sends it in chunks to Discord."""
    for chunk in split_message_for_discord(message):
        await channel.send(chunk)
