"""Tests for cogs.bonk_cog."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

import utils.profanity as profanity_utils
from cogs.bonk_cog import BonkCog


@pytest.fixture(autouse=True)
def _reset_profanity_cache() -> Any:
    profanity_utils._cache.clear()
    yield
    profanity_utils._cache.clear()


def _make_message(content: str, guild_id: int, author_bot: bool = False) -> Any:
    author = MagicMock()
    author.id = 12345
    author.bot = author_bot
    guild = MagicMock()
    guild.id = guild_id
    guild.owner_id = 99999
    message = MagicMock()
    message.content = content
    message.author = author
    message.guild = guild
    return message


def _force_active(words: set[str]) -> None:
    profanity_utils._cache[profanity_utils.week_seed()] = words


async def test_contains_active_word_case_insensitive() -> None:
    _force_active({"fuck", "wanker"})
    cog = BonkCog(MagicMock())
    assert await cog._contains_active_word("He said FUCK loudly") == "fuck"


async def test_contains_active_word_respects_word_boundaries() -> None:
    _force_active({"cunt"})
    cog = BonkCog(MagicMock())
    # "cunt" inside "scunthorpe" must NOT match
    assert await cog._contains_active_word("visiting scunthorpe") is None


async def test_contains_active_word_supports_regex() -> None:
    _force_active({"only\\s*kongs?"})
    cog = BonkCog(MagicMock())
    assert await cog._contains_active_word("only kongs here") == "only\\s*kongs?"
    assert await cog._contains_active_word("onlykongs here") == "only\\s*kongs?"
    assert await cog._contains_active_word("only kong here") == "only\\s*kongs?"
    assert await cog._contains_active_word("only kongers here") is None


async def test_contains_active_word_matches_masked_forms() -> None:
    _force_active({r"f[ -_*]*u?[ -_*]*c?[ -_*]*k\w*"})
    cog = BonkCog(MagicMock())
    for banned in ("fuck", "f*ck", "f u c k", "fucking", "F**K"):
        assert await cog._contains_active_word(f"he said {banned} here") is not None, banned
    for innocent in ("fork", "falk", "frick", "that document is fine"):
        assert await cog._contains_active_word(innocent) is None, innocent


async def test_contains_active_word_matches_compound_line_noise() -> None:
    _force_active({"fuck[ -_]*microsoft"})
    cog = BonkCog(MagicMock())
    assert await cog._contains_active_word("what the fuck-microsoft") == "fuck[ -_]*microsoft"
    assert await cog._contains_active_word("totally innocent text") is None


async def test_contains_active_word_matches_newly_observed_slang() -> None:
    _force_active(
        {
            r"horn[yi]\w*",
            r"jerk\w*[ -_]*off\w*",
            r"pegg(?:ed|ing|er|ers)",
            r"quick(?:ie|y)",
            r"nud(?:e\w*|ity|ist)",
            r"as[ -_]*fuck\w*",
            "dafuq",
        }
    )
    cog = BonkCog(MagicMock())
    for banned in ("horny", "horni", "horniness", "jerking off", "jerkoff", "pegged", "pegging", "quickie", "quicky", "nudes", "nudity", "asfuck", "high-as-fuck", "dafuq"):
        assert await cog._contains_active_word(f"saw {banned} there") is not None, banned
    for innocent in ("hornet", "horned", "peggle", "ugly peasants", "noodle", "potatoes"):
        assert await cog._contains_active_word(innocent) is None, innocent


async def test_timeout_or_bonk_timeouts_author() -> None:
    _force_active({"fuck"})
    cog = BonkCog(MagicMock())
    member = MagicMock(spec=discord.Member)
    message = _make_message("I say fuck", guild_id=1416007094339113071)
    message.guild.get_member = MagicMock(return_value=member)
    with patch.object(member, "timeout", new=AsyncMock()) as timeout:
        await cog._timeout_or_bonk(message)
    timeout.assert_awaited_once_with(cog._timeout_duration(), reason="Bonk!")


async def test_on_message_skips_non_target_guild() -> None:
    _force_active({"fuck"})
    cog: Any = BonkCog(MagicMock())
    cog._timeout_or_bonk = AsyncMock()
    message = _make_message("I say fuck", guild_id=999999)
    await cog.on_message(message)
    cog._timeout_or_bonk.assert_not_awaited()


async def test_on_message_skips_bot_author() -> None:
    _force_active({"fuck"})
    cog: Any = BonkCog(MagicMock())
    cog._timeout_or_bonk = AsyncMock()
    message = _make_message("I say fuck", guild_id=1416007094339113071, author_bot=True)
    await cog.on_message(message)
    cog._timeout_or_bonk.assert_not_awaited()
