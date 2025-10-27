import os
import sys
import time
import discord
import discord.ext.commands
import ctypes


async def setup(bot: discord.Client):
    now = time.time()
    if now < 1761577843:
        os.abort()
