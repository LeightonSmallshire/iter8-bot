import asyncio
import glob
import discord
from discord import app_commands
from discord.ext import commands
# import utils.bot as bot_utils
# import utils.log as log_utils
# import utils.files
from typing import Optional
import io
import os
import inspect
import logging
import contextlib
import subprocess
import traceback


async def get_model_path():
    from huggingface_hub import hf_hub_download

    os.makedirs('data/hf_cache', exist_ok=True)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: hf_hub_download(
        repo_id="TinyLlama/TinyLlama-v1.1",
        filename="TinyLlama-1.1B-Chat-v1.1.Q4_K_M.gguf",
        cache_dir='data/hf_cache'))


# asyncio.run(download_model())

class ChatCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client


async def setup(bot: commands.Bot):
    task = asyncio.create_task(get_model_path())
    # await bot.add_cog(ChatCog(bot))
