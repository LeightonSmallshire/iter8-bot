"""Typed storage keys for aiohttp application and request state."""

import aiohttp
import discord
from aiohttp import web

HTTP_KEY: web.AppKey[aiohttp.ClientSession] = web.AppKey("http", aiohttp.ClientSession)
BOT_KEY: web.AppKey[discord.Client] = web.AppKey("bot", discord.Client)
