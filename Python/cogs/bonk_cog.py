import datetime

import discord
import logfire
from discord import app_commands
from discord.ext import commands

import utils.allowlist as allowlist
import utils.bot as bot_utils
import utils.profanity as profanity_utils

_log = logfire

BONK_MESSAGE = ":bonk: Bonk!"
BONK_EMOJI = "<:bonk:1473609891263549533>"


class BonkCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")
        active = profanity_utils.active_words()
        _log.info(f"Selected words for {profanity_utils.week_seed()}: {sorted(active)}")

    # --- Listeners (Events) ---

    @staticmethod
    def _timeout_duration() -> datetime.timedelta:
        return datetime.timedelta(minutes=5)

    async def _is_exempt(self, message: discord.Message) -> bool:
        """Users we should never timeout: bots, the server owner, and the bot itself."""
        guild = message.guild
        return message.author.bot or guild is None or guild.owner_id == message.author.id

    async def _contains_active_word(self, text: str) -> str | None:
        """Return the first active regex pattern found in the text (else None)."""
        pattern, sources = profanity_utils.active_pattern()
        match = pattern.search(text.lower())
        if match is None or match.lastgroup is None:
            return None
        return sources.get(match.lastgroup, match.group())

    async def _react(self, message: discord.Message) -> None:
        """React to the offending message with the bonk emoji."""
        try:
            await message.add_reaction(BONK_EMOJI)
        except discord.HTTPException as e:
            _log.warning(f'Failed to react to message {message.id}: {e}')

    async def _timeout_or_bonk(self, message: discord.Message) -> None:
        """Timeout the message author for saying an active word."""
        author = message.author
        member = message.guild.get_member(author.id) if message.guild else None
        if not isinstance(member, discord.Member):
            return
        word = await self._contains_active_word(message.content)
        if word is None:
            return

        await self._react(message)

        try:
            await member.timeout(
                self._timeout_duration(),
                reason=BONK_MESSAGE,
            )
            _log.info(f'Bonked {member} ({member.id}) for "{word}"')
        except discord.Forbidden:
            _log.warning(f'Bot lacks permission to timeout {member} ({member.id})')
        except discord.HTTPException as e:
            _log.error(f'Failed to timeout {member} ({member.id}): {e}')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.guild.id != bot_utils.Guilds.Default:
            return

        if self.bot_.user is None:
            return

        if message.author.id == self.bot_.user.id:
            return

        if not allowlist.is_allowed(message.author.id):
            return

        if await self._is_exempt(message):
            return

        await self._timeout_or_bonk(message)

    # --- Local Command Error Handler ---

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message("You don't have the necessary permissions to run this command.")
        elif isinstance(error, commands.CommandNotFound):
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
    await bot.add_cog(BonkCog(bot))
