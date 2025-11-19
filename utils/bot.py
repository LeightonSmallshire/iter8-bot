import logging
import discord
import random
import asyncio
import datetime
import secrets
from typing import Optional
from .model import User


class Guilds:
    TestServer = 1427287847085281382
    Paradise = 1416007094339113071
    Innov8 = 1325821294427766784
    Innov8_DevOps = 1425873966035238975


class Users:
    Nathan = 1326156803108503566
    Leighton = 1416017385596653649
    Charlotte = 1401855871633330349
    Ed = 1356197937520181339
    Matt = 1333425159729840188
    Tom = 1339198017324187681

    @staticmethod
    def all_users():
        ids = [v for k, v in vars(Users).items()
               if isinstance(v, int) and not k.startswith("__")]
        return list(dict.fromkeys(ids))

    @staticmethod
    def random(filter: list[int] = []):
        ids = {v for k, v in vars(Users).items() if isinstance(v, int)}
        for f in filter:
            ids.discard(f)
        if not ids:
            raise ValueError("No users available after exclusion.")
        return random.choice(list(ids))


class Channels:
    TestServerBotSpam = 1432698704191815680
    ParadiseBotBrokenSpam = 1427971106920202240
    ParadiseClockwork = 1416059475873239181
    TestServerStockSpam = 1440731650307915816
    TestServerStockSummary = 1440731630070403284
    StockMarketSpam = 1440735818644852829
    StockMarketSummary = 1440735818644852829


class Roles:
    Admin = 1416037888847511646
    DiceRoller = 1430187659678187581
    BullyTarget = 1432752493670170624


def is_guild_paradise(ctx):
    return ctx.guild and ctx.guild.id == Guilds.Paradise


async def is_user_role(ctx: discord.Interaction, role_id: int):
    guild = ctx.guild
    member = guild.get_member(ctx.user.id) or await guild.fetch_member(ctx.user.id)
    role = guild.get_role(role_id) or await guild.fetch_role(role_id)
    return role in member.roles


def is_trusted_developer(ctx: discord.Interaction):
    return ctx.user.id in [Users.Leighton, Users.Nathan]


def get_non_bot_users(ctx: discord.Interaction) -> list[int]:
    return [x.id for x in ctx.guild.members if not x.bot and x.id != ctx.guild.owner_id]

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


def make_emoji_number(num: int):
    return "".join([f":number_{d}:" for d in str(num)])

async def do_role_roll(interaction:discord.Interaction, role_id: int, roll_table: list[int], embed_title: str, response: tuple[str, str]) -> int:
    ROLL_GIF_URL = "https://media.tenor.com/XYkAxffY_PsAAAAM/dice-bae-dice.gif"

    role = interaction.guild.get_role(role_id) or await interaction.guild.fetch_role(role_id)
    prev_user = role.members[0] if role.members else None

    list_embed = discord.Embed(title=embed_title, color=discord.Color.yellow())
    for idx, user_id in enumerate(roll_table, 1):
        list_embed.add_field(
            name=make_emoji_number(idx),
            value=f"<@{user_id}>",
            inline=False,
        )

    await interaction.followup.send(content=f"@everyone", embed=list_embed, allowed_mentions=discord.AllowedMentions(roles=True))

    if not roll_table:
        await interaction.followup.send(content="There are no users for this roll.")
        return 0
    
    await asyncio.sleep(3)

    roll_embed = discord.Embed(title="Rolling...")
    roll_embed.set_image(url=ROLL_GIF_URL)

    msg = await interaction.followup.send(embed=roll_embed, wait=True)

    # Sleep for dramatic effect
    await asyncio.sleep(4)

    index = secrets.randbelow(len(roll_table))
    # index = random.randrange(0, len(roll_table))
    await msg.edit(content=f"A {make_emoji_number(index + 1)} was rolled!", embed=None)
    print('Roll Table:', *roll_table, index, sep='\n\t')

    await asyncio.sleep(3)

    choice = roll_table[index]
    new_user = await interaction.guild.fetch_member(choice)

    if prev_user is not None:
        await prev_user.remove_roles(role)

    await new_user.add_roles(role)

    message_contents = response[0].format(prev_user.id, choice) if prev_user else response[1].format(choice)
    await msg.edit(content=message_contents)

    return new_user.id

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
            if user and not user.bot:
                if len(message) > 1950:
                    message = message[:1950] + "\n... (truncated)"

                await user.send(f"**Bot Log: ** ```{message}```")
        except discord.errors.NotFound:
            print(f"Error: Could not find user with ID {self.user_id}")
        except Exception as e:
            print(f"Failed to send error DM: {e}")


async def get_timeout_data(guild: discord.Guild | None) -> list[User]:
    if guild is None:
        return []

    leaderboard: list[User] = [User(x.id, 0, 0) for x in guild.members if not x.bot and x.id != guild.owner_id]

    async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
        member = entry.target

        if member not in guild.members:
            continue

        if member.bot or member.id == guild.owner_id:
            continue

        was_timeout = getattr(entry.changes.before, 'timed_out_until', None)
        now_timeout = getattr(entry.changes.after, 'timed_out_until', None)
        was_timeout = was_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
        now_timeout = now_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)

        b_was_timeout = (was_timeout >= entry.created_at)
        b_now_timeout = (now_timeout >= entry.created_at)

        timeout_added = not b_was_timeout and b_now_timeout
        timeout_changed = b_was_timeout and b_now_timeout
        timeout_removed = b_was_timeout and not b_now_timeout
        
        moderator = entry.user
        if (timeout_added or timeout_changed) and moderator == guild.owner:
            continue

        if timeout_added:
            duration = (now_timeout - entry.created_at).total_seconds()
            leaderboard.append(User(member.id, 1, duration))

        if timeout_changed:
            duration = (now_timeout - was_timeout).total_seconds()
            leaderboard.append(User(member.id, 0, duration))

        if timeout_removed:
            duration = (entry.created_at - was_timeout).total_seconds()
            leaderboard.append(User(member.id, 0, duration))

    acc: dict[int, User] = {}
    for t in leaderboard:
        if t.id in acc:
            acc[t.id].count += t.count
            acc[t.id].duration += t.duration
        else:
            acc[t.id] = User(t.id, t.count, t.duration)

    sorted_leaderboard = sorted(
        acc.values(),
        key=lambda x: x.count,
        reverse=True
    )

    return sorted_leaderboard
