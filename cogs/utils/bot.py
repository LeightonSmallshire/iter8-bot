import logging
import discord
import operator
import asyncio
import datetime
from typing import Dict
from .model import Timeout


class Guilds:
    Paradise = 1416007094339113071
    Innov8 = 1325821294427766784
    Innov8_DevOps = 1425873966035238975
    TestServer = 1427287847085281382


class Users:
    Nathan = 1326156803108503566
    Leighton = 1416017385596653649
    Charlotte = 1401855871633330349
    Ed = 1356197937520181339
    Matt = 1333425159729840188
    Tom = 1339198017324187681


class Channels:
    ParadiseBotBrokenSpam = 1427971106920202240
    ParadiseClockwork = 1416059475873239181
    TestServerBotSpam = 1432698704191815680


def is_guild_paradise(ctx):
    return ctx.guild and ctx.guild.id == Guilds.Paradise


def is_trusted_developer(ctx: discord.Interaction):
    return ctx.user.id in [Users.Leighton, Users.Nathan]


# async def send_dm_to_user(bot, user_id, message):
#     try:
#         # Use fetch_user to get the user object from Discord API
#         user = await bot.fetch_user(user_id)

#         if user:
#             # Create a DM channel and send the message
#             await user.send(message)
#             print(f"Successfully sent DM to {user.name} ({user_id})")
#         else:
#             print(f"Could not find user with ID: {user_id}")

#     except discord.errors.NotFound:
#         print(f"User with ID {user_id} not found on Discord.")
#     except Exception as e:
#         print(f"An error occurred while sending DM: {e}")


async def send_message(bot, user_id, message):
    while not bot.is_ready():
        await asyncio.sleep(1)

    paradise = discord.utils.get(bot.guilds, id=Guilds.Paradise)
    if paradise is None:
        return logging.error('could not find paradise')
    user = discord.utils.get(paradise.members, id=user_id)
    if user is None:
        return logging.error('could not find user')

    while True:
        try:
            return await user.send(message)
        except discord.errors.HTTPException as e:
            if 'You are opening direct messages too fast' not in repr(e):
                raise e
            await asyncio.sleep(1)


def defer_message(bot, user_id, message):
    asyncio.create_task(send_message(bot, user_id, message))


class DiscordHandler(logging.Handler):
    def __init__(self, bot: discord.Client, user_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.user_id = user_id

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.loop.create_task(self.send_dm(log_entry))

    async def send_dm(self, message):
        # Nothing to see here
        while not self.bot.is_ready():
            await asyncio.sleep(1)

        try:
            paradise = discord.utils.get(self.bot.guilds, id=Guilds.Paradise)
            user = discord.utils.get(paradise.members, id=Users.Leighton)
            # await leighton.send('setup')

            # user = await self.bot.fetch_user(self.user_id)
            if user:
                if len(message) > 1950:
                    message = message[:1950] + "\n... (truncated)"

                await user.send(f"**Bot Log: ** ```{message}```")
        except discord.errors.NotFound:
            print(f"Error: Could not find user with ID {self.user_id}")
        except Exception as e:
            print(f"Failed to send error DM: {e}")


async def get_timeout_data(guild: discord.Guild | None) -> list[Timeout]:
    if guild is None:
        return []

    leaderboard: list[Timeout] = []

    async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
        member = entry.target

        was_timeout = getattr(entry.changes.before, 'timed_out_until', None)
        now_timeout = getattr(entry.changes.after, 'timed_out_until', None)
        was_timeout = was_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
        now_timeout = now_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)

        b_was_timeout = (was_timeout >= entry.created_at)
        b_now_timeout = (now_timeout >= entry.created_at)

        timeout_added = not b_was_timeout and b_now_timeout
        timeout_changed = b_was_timeout and b_now_timeout
        timeout_removed = b_was_timeout and not b_now_timeout

        if timeout_added:
            duration = (now_timeout - entry.created_at).total_seconds()
            # print('added', duration)
            leaderboard.append(Timeout(member.id, 1, duration))

        if timeout_changed:
            duration = (now_timeout - was_timeout).total_seconds()
            # print('changed', duration)
            leaderboard.append(Timeout(member.id, 0, duration))

        if timeout_removed:
            duration = (entry.created_at - was_timeout).total_seconds()
            # print('removed', duration)
            leaderboard.append(Timeout(member.id, 0, duration))

    acc: dict[int, Timeout] = {}
    for t in leaderboard:
        if t.id in acc:
            acc[t.id].count += t.count
            acc[t.id].duration += t.duration
        else:
            acc[t.id] = Timeout(t.id, t.count, t.duration)

    sorted_leaderboard = sorted(
        acc.values(),
        key=lambda x: x.count,
        reverse=True
    )

    return sorted_leaderboard
