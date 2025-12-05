# import asyncio
# import glob
# import discord
# from discord import app_commands
# from discord.ext import commands
# import utils.bot as bot_utils
# import utils.log as log_utils
# # import utils.files
# from typing import Optional
# import io
# import os
# import inspect
# import logging
# import contextlib
# import subprocess
# import traceback
# from ctransformers import AutoModelForCausalLM, LLM
#
# _log = logging.getLogger(__name__)
# _log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
# _log.addHandler(log_utils.DatabaseHandler())
#
#
# class ChatCog(commands.Cog):
#     def __init__(self, client: discord.Client):
#         self.bot_ = client
#         self.model_: Optional[LLM] = None
#         asyncio.create_task(self._init_model())
#
#     async def _init_model(self):
#         from huggingface_hub import hf_hub_download
#
#         _log.info('chat model loading...')
#
#         model_path = await asyncio.to_thread(
#             hf_hub_download,
#             repo_id="TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
#             filename="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
#             cache_dir='./data/hf_cache')
#
#         self.model_ = await asyncio.to_thread(
#             AutoModelForCausalLM.from_pretrained,
#             model_path,
#             model_type="llama")
#
#         _log.info('chat model loaded')
#
#     @app_commands.command(name="chat")
#     async def chat(self, interaction: discord.Interaction, prompt: str):
#         if self.model_ is None:
#             return await interaction.response.send_message('Model still loading...', ephemeral=True)
#
#         await interaction.response.defer(ephemeral=True)
#
#         # u_prompt = (f'User: {prompt}\r\n'
#         #             f'Assistant: ')
#         u_prompt = (f'### Instruction:\r\n'
#                     f'{prompt}\r\n'
#                     f'\r\n'
#                     f'### Response:\r\n')
#
#         buf = io.StringIO()
#         for token in self.model_(u_prompt, max_new_tokens=200, stream=True, stop=['\n', 'User:', '###']):
#             print(token, end='')
#             buf.write(token)
#
#         # response = await asyncio.to_thread(self.model_.generate, u_prompt, max_new_tokens=100, stream=True)
#         response = buf.getvalue()
#
#         await interaction.followup.send(response)
#
#
# async def setup(bot: commands.Bot):
#     # if bot_utils.IS_TESTING:
#     #     return print('SKIPPING CHAT COG')
#
#     await bot.add_cog(ChatCog(bot))
