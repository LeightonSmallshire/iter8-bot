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
