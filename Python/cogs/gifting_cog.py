import discord
from discord.ext import commands
from discord import app_commands
import logging
import datetime

import utils.bot as bot_utils
import utils.gifts as gift_utils
import utils.shop as shop_utils
import utils.log as log_utils

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())

GIFT_EMOJI_VALUES: dict[str, int] = {
    "🥇": 600, 
    "🥈": 300, 
    "🥉": 60
} 


class GiftingCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Listeners (Events) ---

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if self.bot_.user is None or payload.user_id == self.bot_.user.id:
            return

        if payload.guild_id is None:
            return

        guild = self.bot_.get_guild(payload.guild_id)
        if guild is None:
            return

        if payload.channel_id is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return

        if not isinstance(channel, discord.TextChannel):
            return

        if payload.message_id is None:
            return

        message = await channel.fetch_message(payload.message_id)

        if (message.author.bot or message.author.id == guild.owner_id):
            return
        
        if (payload.user_id == message.author.id):
            return

        emoji_str = str(payload.emoji)
        if emoji_str not in GIFT_EMOJI_VALUES:
            return
        
        gift_value = GIFT_EMOJI_VALUES[emoji_str]

        if not await shop_utils.can_afford_purchase(payload.user_id, gift_value):
            return

        await gift_utils.add_gift(payload.user_id, message.author.id, gift_value)

        await channel.send(f"<@{payload.user_id}> gifted <@{message.author.id}> {datetime.timedelta(seconds=gift_value)} for this message.", reference=message, mention_author=False)
        

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if self.bot_.user is None or payload.user_id == self.bot_.user.id:
            return

        if payload.guild_id is None:
            return

        guild = self.bot_.get_guild(payload.guild_id)
        if guild is None:
            return

        if payload.channel_id is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return

        if not isinstance(channel, discord.TextChannel):
            return

        if payload.message_id is None:
            return

        message = await channel.fetch_message(payload.message_id)

        emoji_str = str(payload.emoji)
        if emoji_str not in GIFT_EMOJI_VALUES:
            return
        
        gift_value = GIFT_EMOJI_VALUES[emoji_str]

        if not await gift_utils.did_gift(payload.user_id, message.author.id, gift_value):
            return

        await gift_utils.add_gift(payload.user_id, message.author.id, -gift_value)

        await channel.send(f"<@{payload.user_id}> took away their gift <@{message.author.id}> for this message.", reference=message)


    # --- Local Command Error Handler (Overrides the global handler for this cog's commands) ---

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """
        Handles errors specifically for commands defined within this cog.
        Note: This specific function is for handling prefix command errors.
        For slash commands, errors are often handled via `on_app_command_error`.
        """
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message("You don't have the necessary permissions to run this command.")
        elif isinstance(error, commands.CommandNotFound):
            # This generally won't happen if the command is correctly registered
            pass
        else:
            msg = f'An unhandled command error occurred in cog {self.qualified_name}: {error}'
            _log.error(msg)
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


# --- Cog Setup Function (MANDATORY for extensions) ---


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiftingCog(bot))
