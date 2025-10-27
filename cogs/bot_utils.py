import logging
import discord
import asyncio


class Guilds:
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


def is_guild_paradise(ctx):
    return ctx.guild and ctx.guild.id == Guilds.Paradise


class Channels:
    ParadiseBotBrokenSpam = 1427971106920202240


async def send_dm_to_user(self, user_id, message):
    try:
        # Use fetch_user to get the user object from Discord API
        user = await self.bot.fetch_user(user_id)

        if user:
            # Create a DM channel and send the message
            await user.send(message)
            print(f"Successfully sent DM to {user.name} ({user_id})")
        else:
            print(f"Could not find user with ID: {user_id}")

    except discord.errors.NotFound:
        print(f"User with ID {user_id} not found on Discord.")
    except Exception as e:
        print(f"An error occurred while sending DM: {e}")


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
            user = await self.bot.fetch_user(self.user_id)
            if user:
                if len(message) > 1950:
                    message = message[:1950] + "\n... (truncated)"

                await user.send(f"**Bot Log: ** ```{message}```")
        except discord.errors.NotFound:
            print(f"Error: Could not find user with ID {self.user_id}")
        except Exception as e:
            print(f"Failed to send error DM: {e}")
