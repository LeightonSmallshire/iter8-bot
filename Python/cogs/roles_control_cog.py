import asyncio
import glob
import discord
from discord import app_commands
from discord.ext import commands
import utils.bot as bot_utils
import utils.log as log_utils
import utils.files
from typing import Optional
import io
import os
import inspect
import logging
import contextlib
import subprocess
import traceback
import sys

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())


class RoleControlCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()

    @app_commands.command(name='show_perms', description="Shows all permissions for all roles and users")
    @commands.check(bot_utils.is_guild_paradise)
    async def do_show_perms(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        report = f"Permissions Report for {guild.name}\n"
        report += "="*30 + "\n\n"

        # --- Role Permissions ---
        report += "### ROLE PERMISSIONS ###\n"
        for role in sorted(guild.roles, reverse=True):
            enabled_perms = [p[0] for p in role.permissions if p[1]]
            report += f"Role: {role.name} (ID: {role.id})\n"
            report += f"Perms: {', '.join(enabled_perms) if enabled_perms else 'None'}\n"
            report += "-"*20 + "\n"

        report += "\n" + "#"*30 + "\n\n"

        # --- Member Permissions ---
        report += "### MEMBER PERMISSIONS ###\n"
        # Note: Depending on server size, you might want to limit this or use a generator
        async for member in guild.fetch_members(limit=None):
            enabled_perms = [p[0] for p in member.guild_permissions if p[1]]
            report += f"Member: {member.display_name} ({member.name}#{member.discriminator})\n"
            report += f"Perms: {', '.join(enabled_perms) if enabled_perms else 'None'}\n"
            report += "-"*20 + "\n"

        # Create a file-like object in memory
        buffer = io.BytesIO(report.encode('utf-8'))
        file = discord.File(fp=buffer, filename=f"{guild.id}_permissions.txt")

        # Send the file
        await interaction.followup.send(content="Permissions report:", file=file, ephemeral=True)
        

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleControlCog(bot))
