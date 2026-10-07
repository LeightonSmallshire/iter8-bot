"""Register the Discord Activity launch command.

Discord exposes an Activity to clients through a *primary entry point* command: an
application-level command of type ``4`` (``PRIMARY_ENTRY_POINT``) named ``launch``.
discord.py 2.7.1 has no model for it -- ``app_commands.Command`` cannot express the type --
so it is registered over the REST API instead.

It has to be re-registered on every startup. The hot-reload flow rewrites the guild's
commands on each reload, and anything added by hand in the developer portal does not
survive that.
"""

from typing import Any

import aiohttp
import discord
import logfire

from utils.bot import API_USER_AGENT

# Application command type for a primary entry point ("launch" / "link" activities).
PRIMARY_ENTRY_POINT = 4

COMMANDS_URL = "https://discord.com/api/v10/applications/{application_id}/commands"

LAUNCH_NAME = "launch"
LAUNCH_DESCRIPTION = "Open the shop, credits and gig finder"

# Primary entry points are shown per-locale, so give the ones we can speak. Without these
# the command only appears under the application's default locale.
LOCALES = ("en-GB", "en-US")


def launch_command_payload(
    application_id: str,
    name: str = LAUNCH_NAME,
    description: str = LAUNCH_DESCRIPTION,
) -> dict[str, Any]:
    """The JSON body for creating the launch command."""
    return {
        "name": name,
        "type": PRIMARY_ENTRY_POINT,
        "application_id": application_id,
        "description": description,
        "name_localizations": dict.fromkeys(LOCALES, name),
        "description_localizations": dict.fromkeys(LOCALES, description),
    }


def needs_launch_command(commands: list[dict[str, Any]], name: str = LAUNCH_NAME) -> bool:
    """True when the launch command is absent or stale and must be created.

    discord.py cannot represent a primary entry point, so it will never appear in the
    command tree and is never touched by ``tree.sync``; a plain chat-input command of the
    same name would be a different thing and must not be mistaken for it.
    """
    existing = next((c for c in commands if c.get("name") == name), None)
    if existing is None:
        return True
    return existing.get("type") != PRIMARY_ENTRY_POINT


async def ensure_launch_command(bot: discord.Client, session: aiohttp.ClientSession | None = None) -> bool:
    """Create the launch command if it is not already registered.

    Returns True when a command was created. Never raises: a missing scope or a Discord
    outage should not stop the bot from coming up.
    """
    application_id = str(bot.application_id)
    if not application_id or application_id == "0":
        logfire.warning("Cannot register the activity launch command: no application id.")
        return False

    headers = {"Authorization": f"Bot {bot.http.token}", "User-Agent": API_USER_AGENT}

    async def call(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        async with session_or_new(session) as http, http.request(method, url, json=payload, headers=headers) as response:
            try:
                return response.status, await response.json(content_type=None)
            except ValueError:
                return response.status, None

    try:
        status, existing = await call("GET", COMMANDS_URL.format(application_id=application_id))
        if status != 200 or not isinstance(existing, list):
            logfire.warning(f"Could not list application commands (HTTP {status}); launch command not registered.")
            return False

        if not needs_launch_command(cast_list(existing)):
            logfire.info("Activity launch command already registered.")
            return False

        payload = launch_command_payload(application_id)
        status, body = await call("POST", COMMANDS_URL.format(application_id=application_id), payload)
        if status not in (200, 201):
            logfire.warning(f"Could not register the activity launch command (HTTP {status}): {body}")
            return False

        logfire.info(f"Registered activity launch command /{LAUNCH_NAME} ({application_id}).")
        return True
    except aiohttp.ClientError as exc:
        logfire.warning(f"Could not reach Discord to register the launch command: {exc}")
        return False


def cast_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def session_or_new(session: aiohttp.ClientSession | None) -> Any:
    """Return a reusable session, or a short-lived one."""
    if session is not None:
        return _Borrowed(session)
    return _Owned()


class _Borrowed:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def __aenter__(self) -> aiohttp.ClientSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class _Owned:
    async def __aenter__(self) -> aiohttp.ClientSession:
        self._session = aiohttp.ClientSession(headers={"User-Agent": API_USER_AGENT})
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        await self._session.close()
        return None
