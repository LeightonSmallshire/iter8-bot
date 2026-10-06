"""Weekly-rotating "bonk" profanity filter.

Each week a deterministic seed is derived from the current ISO calendar week,
and a fixed 10% of the profanity list is selected for enforcement that week.
The selection is stable within a week and changes every Monday.
"""

import datetime
import random
import re
from collections.abc import Iterable

import logfire

_log = logfire

# Fraction of the profanity list enforced in any given week.
ENFORCE_FRACTION = 0.1

# A curated profanity list, focused on sexual profanity and grounded in words
# actually observed in chat (see scan_banlist_tmp.py / word_freq.txt). Common/minor
# cursing (damn, hell, shit, insults) and slurs are excluded — those are handled by
# Discord's own moderation. This cog is fun only.
# Entries are regex patterns. Word-boundary anchors ``\\b`` are added automatically
# around each pattern, and matching is case-insensitive. Use ``[ -_*]*`` to tolerate
# characters/punctuation between letters (leetspeak/masked forms) and ``\w*`` to
# tolerate suffixes (e.g. "fucking", "fuck-microsoft").
PROFANITY_WORDS: list[str] = [
    r"f[ -_*]*u?[ -_*]*c?[ -_*]*k",
    r"mother[\- ]*f[ -_*]*u?[ -_*]*c?[ -_*]*k",
    # Others tolerate a single masked letter (c*nt, d*ck, p*ssy, p*rn).
    r"c[ -_*]*u?[ -_*]*n[ -_*]*t",
    r"p[ -_*]*u?[ -_*]*s[ -_*]*s[ -_*]*y",
    r"d[ -_*]*i?[ -_*]*c[ -_*]*k",
    r"c[ -_*]*o?[ -_*]*c[ -_*]*k",
    r"p[ -_*]*o?[ -_*]*r[ -_*]*n",
    r"w[ -_*]*h[ -_*]*o[ -_*]*r[ -_*]*e",
    r"b[ -_*]*o[ -_*]*o[ -_*]*b",
    r"t[ -_*]*i[ -_*]*t",
    # --- Observed compound line-noise forms ---
    r"fuck[ -_]*this[ -_]*shit[ -_]*im[ -_]*out",
    r"pussy[ -_]*wagon[ -_]*chicken[ -_]*nuggets",
    r"horny[ -_]*jail[ -_]*go[ -_]*to[ -_]*horny[ -_]*jail[ -_]*bonk",
    r"strip[ -_]*tease",
    r"jerk\w*[ -_]*off",
    # --- anatomy ---
    r"twat|minge|vagina|pussies|clit|clitoris",
    r"prick|knob|penis|testicle|scrotum",
    r"tit|titty|jugs|boob",
    r"anal|anus|butthole|arse|booty|ass",
    r"cum|jizz|semen|spunk|sperm",
    # --- acts ---
    r"wank|wanker|wanking",
    r"handjob|blowjob|rimjob",
    r"orgasm",
    r"edging",
    r"spank\w*",
    r"moan|moaning",
    r"twerk",
    r"shag",
    r"pegg(?:ed|ing|er|ers)",
    r"fingering",
    r"undress",
    r"thirst",
    # --- terms ---
    r"slut|slag|skank|slapper",
    r"perv\w*",
    r"masochist",
    r"femboy\w*",
    r"thicc",
    r"mpreg",
    r"horn[yi]\w*",
    r"erotic",
    r"stripper",
    r"safeword",
    r"cuck",
    r"milf",
    r"quick(?:ie|y)",
    r"fetish\w*",
    r"kink\w*",
    # --- items ---
    r"dildo|vibrator|toys",
    r"rope|bondage|shibari",
    r"nud(?:e\w*|ity|ist)|noods",
    # --- misc ---
    r"ballache",
    r"wtf|wtaf",
    r"dafuq",
    r"omfg",
    r"grindr|tinder",
    r"moistness",
    r"only\s*fans",
    # --- phrases ---
    r"(?:me|her|them|him|you) wet",
    r"goth|biker",
    r"lizard|:lizard:|🦎",
    r"smirk|:smirk:|😏",
    r"momm(?:y|ies)",
    r"dadd(?:y|ies)",
    r"mom.*goin.*on",
    r"gf|girlfriend|bf|boyfriend",
]

_cache: dict[int, set[str]] = {}
_pattern_cache: dict[int, tuple[frozenset[str], re.Pattern[str], dict[str, str]]] = {}

# Matches nothing, used when a week somehow ends up with no words selected.
_NEVER_MATCHES = re.compile(r"(?!x)x")


def _ensure_upper_bound(fraction: float) -> int:
    """Return how many words are enforced for the given fraction."""
    return max(1, round(len(PROFANITY_WORDS) * fraction))


def week_seed(day: datetime.date | None = None) -> int:
    """Derive a deterministic seed from the ISO week of the given date."""
    d = day or datetime.date.today()
    year, week, _weekday = d.isocalendar()
    return year * 100 + week


def active_words(day: datetime.date | None = None) -> set[str]:
    """Return the set of profanity words enforced for the current (or given) week."""
    seed = week_seed(day)
    if seed not in _cache:
        rng = random.Random(seed)
        _count = _ensure_upper_bound(ENFORCE_FRACTION)
        _cache[seed] = set(rng.sample(PROFANITY_WORDS, _count))
        _log.debug(f"Bonk filter -> {len(_cache[seed])} words for week seed {seed}")
    return _cache[seed]


def _wrap(subpattern: str) -> str:
    """Lowercase a subpattern and fence it so it cannot match inside a longer word.

    The leading guard is ``(?<!\\w)`` rather than ``\\b`` so that alternatives which
    start on a non-word character (``:lizard:``, an emoji) can still match at a position
    with no word boundary; for a pattern starting on a word character the two guards are
    equivalent. The trailing ``(?!\\w)`` rejects a partial match when the pattern ends on
    ``?``/``*`` (e.g. ``kongs?`` must not match inside "kongers") while remaining
    satisfiable after a non-word character such as an emoji.
    """
    lowered = subpattern.lower()
    return f"(?<!\\w)(?:{lowered})(?!\\w)"


def _group_name(subpattern: str) -> str:
    """Encode a subpattern as a legal regex group name.

    Group names must be valid Python identifiers, so every character outside
    ``[A-Za-z0-9_]`` is escaped as ``_xNN_`` using its byte value. The letters
    survive, so ``pattern.groupindex`` still shows which subpattern is which
    when debugging: ``twat`` stays ``twat``, and ``jerk\\w*[ -_]*off`` becomes
    ``jerk_x5c_w_x5c_w__x5b_20_2d_5f_2a_5d__x2a_off``.
    """
    chars: list[str] = []
    for char in subpattern:
        if char.isascii() and (char.isalnum() or char == "_"):
            chars.append(char)
        else:
            chars.append(f"_x{ord(char):02x}_")
    name = "".join(chars)
    if not name or name[0].isdigit():
        name = f"p{name}"
    return name


def _compile(words: Iterable[str]) -> tuple[re.Pattern[str], dict[str, str]]:
    """Combine the given subpatterns into one matcher, tracking which one matched."""
    sources: dict[str, str] = {}
    parts: list[str] = []
    for subpattern in sorted(words):
        base = _group_name(subpattern)
        name = base
        attempt = 0
        while name in sources:
            attempt += 1
            name = f"{base}_{attempt}"
        sources[name] = subpattern
        parts.append(f"(?P<{name}>{_wrap(subpattern)})")
    if not parts:
        return _NEVER_MATCHES, sources
    return re.compile("|".join(parts)), sources


def active_pattern(day: datetime.date | None = None) -> tuple[re.Pattern[str], dict[str, str]]:
    """Return this week's combined matcher plus a group-name -> subpattern map.

    Each named group's name encodes the subpattern it came from (see
    :func:`_group_name`), so a match can be traced back to its source. The compiled
    result is cached against the exact word set it was built from, so a changed
    selection can never leave a stale matcher behind.
    """
    seed = week_seed(day)
    words = frozenset(active_words(day))
    cached = _pattern_cache.get(seed)
    if cached is None or cached[0] != words:
        pattern, sources = _compile(words)
        _pattern_cache[seed] = (words, pattern, sources)
        return pattern, sources
    return cached[1], cached[2]
