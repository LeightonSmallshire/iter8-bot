"""Hard-coded allowlist of members permitted to interact with the bot.

Source: member list of Paradise (guild 1416007094339113071), fetched once.
Only members on this list may use any bot feature, in any guild or DM.
"""

import discord
from discord.ext import commands

ALLOWED_USERS: dict[int, str] = {
    1326156803108503566: "nathan_15867 (Happy Nathan (Dirty Chef))",
    1333425159729840188: "i8mblackburn (Matt (Anime Girl))",
    1339198017324187681: "thomas_millard_45561 (Tom (Local Weirdboyz))",
    134073775925886976: "MathBot (bot)",
    1356197937520181339: "edwardc_61419 (Ed (HoppEd))",
    1359152866727821342: "gary_27334 (Gary (Gym Bro))",
    1401855871633330349: "charlottewitts_48034 (Zarlotte (Wingwoman))",
    1416017385596653649: "leighton_73312 (Leighton (BikerBoi))",
    1425483577587531886: "Clockwork (bot, self)",
    1429771278239404052: "YouTube Bot (bot)",
    1434869160990736505: "fifthed (AI)",
}

ALLOWED_IDS: frozenset[int] = frozenset(ALLOWED_USERS)


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_IDS


def is_allowed_prefix(ctx: commands.Context[commands.Bot]) -> bool:
    """Global check for prefix (!) commands."""
    return is_allowed(ctx.author.id)


async def deny_if_not_allowed(interaction: discord.Interaction) -> bool:
    """For CommandTree.interaction_check: respond and deny strangers.

    Returning False makes the tree return early — no error handlers fire,
    so the user sees exactly this one message.
    """
    if is_allowed(interaction.user.id):
        return True
    if not interaction.response.is_done():
        await interaction.response.send_message(
            "You're not on the list. Ask a Paradise member to add you.",
            ephemeral=True,
        )
    return False
