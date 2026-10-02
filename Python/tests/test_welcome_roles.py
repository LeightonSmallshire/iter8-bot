"""Tests for cogs.welcome_cog: role diffing, checkbox modal payload, and welcome overwrites."""

import types
from typing import cast

import discord
import pytest
from discord.ext import commands

import cogs.welcome_cog as welcome_cog
from cogs.welcome_cog import (
    GROUP_CUSTOM_ID,
    MODAL_CUSTOM_ID,
    PICK_CUSTOM_ID,
    ROLE_CHANNELS,
    RolePickerModal,
    WelcomeCog,
    WelcomeView,
    _option_description,
    _resolve_gate_roles,
    _role_diff,
)


class FakeBot:
    pass


class FakeRole:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_cog() -> WelcomeCog:
    return WelcomeCog(cast(commands.Bot, FakeBot()))


# --- _role_diff -----------------------------------------------------------------


def test_role_diff_add_remove_parity() -> None:
    to_add, to_remove = _role_diff({"Shitposter", "Worker"}, {"Worker", "Crafter"})
    assert to_add == ["Crafter"]
    assert to_remove == ["Shitposter"]


def test_role_diff_unchanged() -> None:
    assert _role_diff({"NSFW"}, {"NSFW"}) == ([], [])
    assert _role_diff(set(), set()) == ([], [])


def test_role_diff_ignores_non_gate_names() -> None:
    to_add, to_remove = _role_diff({"Admin", "Moderator"}, {"Bogus", "Shitposter"})
    assert to_add == ["Shitposter"]
    assert to_remove == []


def test_role_diff_orders_by_role_channels() -> None:
    to_add, _ = _role_diff(set(), {"NSFW", "Crafter", "Shitposter"})
    assert to_add == ["Shitposter", "Crafter", "NSFW"]


# --- _option_description ---------------------------------------------------------


def test_option_description_unlocks_categories() -> None:
    assert _option_description("Worker") == "Unlocks: Non-Shitposts, Stonks"


def test_option_description_ns_fw_taunt() -> None:
    assert _option_description("NSFW") == "Nothing. You just wanted to see nsfw."


def test_option_description_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(welcome_cog, "ROLE_CHANNELS", {"Long": ["x" * 100]})
    description = _option_description("Long")
    assert description.startswith("Unlocks: ")
    assert len(description) == 100


# --- _resolve_gate_roles ---------------------------------------------------------


def test_resolve_gate_roles_all_present() -> None:
    guild = cast(discord.Guild, types.SimpleNamespace(roles=[FakeRole(name) for name in ROLE_CHANNELS]))
    resolved = _resolve_gate_roles(guild)
    assert resolved is not None
    assert set(resolved) == set(ROLE_CHANNELS)
    assert all(resolved[name].name == name for name in ROLE_CHANNELS)


def test_resolve_gate_roles_missing_returns_none() -> None:
    roles = [FakeRole(name) for name in ROLE_CHANNELS if name != "NSFW"]
    guild = cast(discord.Guild, types.SimpleNamespace(roles=roles))
    assert _resolve_gate_roles(guild) is None


# --- RolePickerModal payload ------------------------------------------------------


def test_modal_persistent() -> None:
    modal = RolePickerModal({"NSFW"})
    assert modal.is_persistent()
    assert modal.timeout is None


def test_modal_payload_structure() -> None:
    payload = RolePickerModal({"NSFW"}).to_dict()
    assert payload["title"] == "Pick your roles"
    assert payload["custom_id"] == MODAL_CUSTOM_ID
    assert len(payload["title"]) <= 45

    label = payload["components"][0]
    assert label["type"] == 18
    assert label["label"] == "Your roles"
    assert label["description"] == "Tick to join, untick to leave."
    assert len(label["label"]) <= 45
    assert len(label["description"]) <= 100

    group = label["component"]
    assert group["type"] == 22
    assert group["custom_id"] == GROUP_CUSTOM_ID
    assert group["min_values"] == 0
    assert group["max_values"] == len(ROLE_CHANNELS)
    assert group["required"] is False

    options = group["options"]
    assert [option["label"] for option in options] == list(ROLE_CHANNELS)
    assert [option["value"] for option in options] == list(ROLE_CHANNELS)
    assert [option.get("default", False) for option in options] == [
        name == "NSFW" for name in ROLE_CHANNELS
    ]
    for option in options:
        assert option["description"]
        assert len(option["label"]) <= 100
        assert len(option["value"]) <= 100
        assert len(option["description"]) <= 100


def test_modal_no_defaults_when_nothing_held() -> None:
    payload = RolePickerModal(set()).to_dict()
    options = payload["components"][0]["component"]["options"]
    assert not any(option.get("default", False) for option in options)


async def test_modal_stop_restores_registration() -> None:
    modal = RolePickerModal(set())
    recorded: list[object] = []
    modal._client = cast(discord.Client, types.SimpleNamespace(add_view=recorded.append))
    modal.stop()
    assert len(recorded) == 1
    restored = recorded[0]
    assert isinstance(restored, RolePickerModal)
    assert restored is not modal
    assert restored.to_dict()["custom_id"] == MODAL_CUSTOM_ID


# --- WelcomeView -----------------------------------------------------------------


def test_welcome_view_single_persistent_button() -> None:
    view = WelcomeView()
    assert view.is_persistent()
    assert len(view.children) == 1
    button = view.children[0]
    assert isinstance(button, discord.ui.Button)
    assert button.custom_id == PICK_CUSTOM_ID
    assert button.label == "Pick your roles"
    assert button.style is discord.ButtonStyle.primary


# --- _welcome_overwrites ----------------------------------------------------------


def test_welcome_overwrites_everyone_read_only() -> None:
    everyone = object()
    me = object()
    guild = cast(discord.Guild, types.SimpleNamespace(default_role=everyone, me=me))
    desired = _make_cog()._welcome_overwrites(guild)
    assert set(desired) == {everyone, me}
    everyone_ow = desired[everyone]
    assert everyone_ow.view_channel is True
    assert everyone_ow.read_message_history is True
    assert everyone_ow.send_messages is False
    assert everyone_ow.send_messages_in_threads is False
    assert everyone_ow.create_public_threads is False
    assert everyone_ow.create_private_threads is False


def test_welcome_overwrites_bot_member_grant() -> None:
    everyone = object()
    me = object()
    guild = cast(discord.Guild, types.SimpleNamespace(default_role=everyone, me=me))
    desired = _make_cog()._welcome_overwrites(guild)
    me_ow = desired[me]
    assert me_ow.view_channel is True
    assert me_ow.read_message_history is True
    assert me_ow.send_messages is True
    assert me_ow.manage_messages is True


def test_welcome_overwrites_without_me() -> None:
    everyone = object()
    guild = cast(discord.Guild, types.SimpleNamespace(default_role=everyone, me=None))
    desired = _make_cog()._welcome_overwrites(guild)
    assert set(desired) == {everyone}
