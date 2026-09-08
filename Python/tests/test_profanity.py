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
