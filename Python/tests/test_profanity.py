"""Tests for utils.profanity (weekly bonk filter)."""
import datetime

from utils import profanity


def test_active_words_are_deterministic_for_a_week() -> None:
    day = datetime.date(2026, 9, 7)
    first = profanity.active_words(day)
    second = profanity.active_words(day)
    assert first == second


def test_active_words_change_across_weeks() -> None:
    week_a = profanity.active_words(datetime.date(2026, 9, 7))
    week_b = profanity.active_words(datetime.date(2026, 9, 14))
    assert week_a != week_b


def test_active_words_is_10_percent_of_list() -> None:
    day = datetime.date(2026, 9, 7)
    active = profanity.active_words(day)
    expected = max(1, round(len(profanity.PROFANITY_WORDS) * profanity.ENFORCE_FRACTION))
    assert len(active) == expected
    assert active.issubset(profanity.PROFANITY_WORDS)


def test_week_seed_deterministic() -> None:
    day = datetime.date(2026, 9, 7)
    assert profanity.week_seed(day) == profanity.week_seed(day)
    assert profanity.week_seed(day) != profanity.week_seed(datetime.date(2026, 9, 14))


def test_full_word_list_compiles() -> None:
    """Every entry must produce a legal group name, however exotic the metacharacters."""
    pattern, sources = profanity._compile(set(profanity.PROFANITY_WORDS))
    assert pattern.groups == len(sources)
    assert set(pattern.groupindex) == set(sources)


def test_group_names_are_identifiers() -> None:
    for word in profanity.PROFANITY_WORDS:
        name = profanity._group_name(word)
        assert name.isidentifier(), word


def test_group_names_round_trip_to_their_subpattern() -> None:
    _pattern, sources = profanity._compile({r"jerk\w*[ -_]*off"})
    assert set(sources.values()) == {r"jerk\w*[ -_]*off"}
    name = next(iter(sources))
    assert "jerk" in name and "off" in name


def test_active_pattern_caches_per_week() -> None:
    day = datetime.date(2026, 9, 7)
    first = profanity.active_pattern(day)
    second = profanity.active_pattern(day)
    assert first[0] is second[0] and first[1] is second[1]


def test_active_pattern_rebuilds_when_words_change() -> None:
    """A regenerated word set must not leave a stale compiled pattern behind."""
    day = datetime.date(2026, 9, 7)
    before = profanity.active_pattern(day)[0]
    profanity._cache.pop(profanity.week_seed(day), None)
    profanity._cache[profanity.week_seed(day)] = {"xylophone"}
    after, sources = profanity.active_pattern(day)
    assert after is not before
    assert after.search("a xylophone") is not None
    assert after.search("anything else") is None
    assert set(sources.values()) == {"xylophone"}


def test_no_word_selected_never_matches() -> None:
    pattern, sources = profanity._compile(set())
    assert sources == {}
    assert pattern.search("literally anything at all") is None


def test_masked_pattern_does_not_match_inside_a_longer_word() -> None:
    pattern, _sources = profanity._compile({r"only\s*kongs?"})
    assert pattern.search("only kongers here") is None
    assert pattern.search("only kong") is not None
    assert pattern.search("onlykongs") is not None


def test_alternatives_starting_on_non_word_characters_match() -> None:
    pattern, _sources = profanity._compile({r"lizard|:lizard:|🦎"})
    assert pattern.search("🦎") is not None
    assert pattern.search(":lizard:") is not None
    assert pattern.search("lizard") is not None
