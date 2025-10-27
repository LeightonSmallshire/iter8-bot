import os
import sys
import time
import discord
import discord.ext.commands
import ctypes


async def setup(bot: discord.Client):
    # await bot_utils.send_dm_to_user(1416017385596653649, 'error incoming')
    now = time.time()
    if now < 1761575246 + 60*5:

        # Try to access memory address 0, which is typically forbidden (NULL pointer dereference)
        # This will usually result in a Segmentation Fault (SIGSEGV)
        ctypes.string_at(0)
        exit(-1)
