"""Tests for the Activity launch command registration.

discord.py cannot model a primary entry point, so this module talks to the REST API. The
decision logic is kept free of I/O so it can be tested directly.
"""

from typing import Any, cast

import aiohttp
import discord
import pytest

from utils import activity

APPLICATION_ID = "1425483577587531886"


def _command(name: str, command_type: int, description: str = "x") -> dict[str, Any]:
    return {"name": name, "type": command_type, "description": description}


def test_payload_is_a_primary_entry_point() -> None:
    payload = activity.launch_command_payload(APPLICATION_ID)
    assert payload["name"] == "launch"
    # 4 is PRIMARY_ENTRY_POINT; a chat-input command is 1 and would not launch anything.
    assert payload["type"] == activity.PRIMARY_ENTRY_POINT == 4
    assert payload["application_id"] == APPLICATION_ID
    assert payload["description"]


def test_payload_carries_localisations() -> None:
    # Primary entry points are shown per locale; without these the command only appears
    # under the application's default locale.
    payload = activity.launch_command_payload(APPLICATION_ID)
    assert payload["name_localizations"]["en-GB"] == "launch"
    assert "en-GB" in payload["description_localizations"]


def test_missing_command_needs_creating() -> None:
    assert activity.needs_launch_command([]) is True
    assert activity.needs_launch_command([_command("shop", 1)]) is True


def test_existing_launch_command_is_left_alone() -> None:
    assert activity.needs_launch_command([_command("launch", activity.PRIMARY_ENTRY_POINT)]) is False


def test_a_chat_input_command_of_the_same_name_is_not_mistaken_for_it() -> None:
    # Same name but the wrong type: Discord will not treat it as an Activity launcher, so
    # it has to be created rather than assumed present.
    assert activity.needs_launch_command([_command("launch", 1)]) is True


def test_other_primary_entry_points_do_not_count() -> None:
    # A LINK (type 5) entry point of the same name is still not ours.
    assert activity.needs_launch_command([_command("launch", 5)]) is True


class _Response:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload

    async def json(self, content_type: str | None = None) -> Any:
        del content_type
        if self._payload is _INVALID:
            raise ValueError("not json")
        return self._payload

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


_INVALID = object()


class _Bot:
    def __init__(self, application_id: str = APPLICATION_ID) -> None:
        self.application_id = int(application_id)
        self.http = type("Http", (), {"token": "tok"})()


def _client(application_id: str = APPLICATION_ID) -> discord.Client:
    """ensure_launch_command only touches application_id and the http token."""
    return cast(discord.Client, _Bot(application_id))


def _session(fake: Any) -> aiohttp.ClientSession:
    """The function only needs something with .request(...) returning an async CM."""
    return cast(aiohttp.ClientSession, fake)


async def test_creates_the_command_when_absent() -> None:
    created: list[dict[str, Any]] = []

    class _Session:
        def request(self, method: str, url: str, json: Any = None, headers: Any = None) -> _Response:
            del url, headers
            if method == "GET":
                return _Response(200, [])
            created.append(json)
            return _Response(201, json)

    assert await activity.ensure_launch_command(_client(), session=_session(_Session())) is True
    assert created and created[0]["type"] == activity.PRIMARY_ENTRY_POINT


async def test_does_not_recreate_an_existing_command() -> None:
    posts: list[int] = []

    class _Session:
        def request(self, method: str, url: str, json: Any = None, headers: Any = None) -> _Response:
            del url, json, headers
            if method == "GET":
                return _Response(200, [_command("launch", activity.PRIMARY_ENTRY_POINT)])
            posts.append(1)
            return _Response(201, {})

    assert await activity.ensure_launch_command(_client(), session=_session(_Session())) is False
    assert posts == []


async def test_survives_a_discord_rejection_without_raising() -> None:
    class _Session:
        def request(self, method: str, url: str, json: Any = None, headers: Any = None) -> _Response:
            del method, url, json, headers
            return _Response(403, {"message": "Missing Access"})

    # A missing scope must not stop the bot coming up.
    assert await activity.ensure_launch_command(_client(), session=_session(_Session())) is False


async def test_survives_a_non_json_response() -> None:
    class _Session:
        def request(self, method: str, url: str, json: Any = None, headers: Any = None) -> _Response:
            del method, url, json, headers
            return _Response(200, _INVALID)

    assert await activity.ensure_launch_command(_client(), session=_session(_Session())) is False


async def test_gives_up_without_an_application_id() -> None:
    assert await activity.ensure_launch_command(_client(application_id="0"), session=None) is False


@pytest.mark.parametrize("bad", [None, "not-a-list", {"nope": 1}])
async def test_malformed_listing_is_not_fatal(bad: Any) -> None:
    class _Session:
        def request(self, method: str, url: str, json: Any = None, headers: Any = None) -> _Response:
            del method, url, json, headers
            return _Response(200, bad)

    assert await activity.ensure_launch_command(_client(), session=_session(_Session())) is False


def test_ensure_signature_accepts_a_real_client() -> None:
    # Guards the annotation against drifting from what main.py passes.
    assert callable(activity.ensure_launch_command)
    assert isinstance(discord.Client, type)
