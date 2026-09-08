"""Weekly-rotating "bonk" profanity filter.

Each week a deterministic seed is derived from the current ISO calendar week,
and a fixed 10% of the profanity list is selected for enforcement that week.
The selection is stable within a week and changes every Monday.
"""

import datetime
import random

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
    # --- Heavy hitters (very common in chat): masked-tolerant ---
    # The fuck family tolerates masking/separators between letters (f*ck, f**k,
    # f u c k, fucking) without matching innocent words like fork/falk/frick.
    # Misspellings like "fuking"/"fckin" and suffixes like "fuckers"/"fuckery"
    # are caught by the optional letters and ``\w*`` tail.
    r"f[ -_*]*u?[ -_*]*c?[ -_*]*k\w*",
    r"mother[\- ]*f[ -_*]*u?[ -_*]*c?[ -_*]*k\w*",
    # Others tolerate a single masked letter (c*nt, d*ck, p*ssy, p*rn).
    r"c[ -_*]*u?[ -_*]*n[ -_*]*t\w*",
    r"p[ -_*]*u?[ -_*]*s[ -_*]*s[ -_*]*y\w*",
    r"d[ -_*]*i?[ -_*]*c[ -_*]*k\w*",
    r"c[ -_*]*o?[ -_*]*c[ -_*]*k\w*",
    r"p[ -_*]*o?[ -_*]*r[ -_*]*n\w*",
    r"w[ -_*]*h[ -_*]*o[ -_*]*r[ -_*]*e\w*",
    r"b[ -_*]*o[ -_*]*o[ -_*]*b\w*",
    r"t[ -_*]*i[ -_*]*t\w*",
    # --- Observed compound line-noise forms ---
    r"fuck[ -_]*this[ -_]*shit[ -_]*im[ -_]*out",
    r"fuck[ -_]*microsoft",
    r"pussy[ -_]*wagon[ -_]*chicken[ -_]*nuggets",
    r"horny[ -_]*jail[ -_]*go[ -_]*to[ -_]*horny[ -_]*jail[ -_]*bonk",
    r"whatever\s*the\s*fuck\w*",
    r"as[ -_]*fuck\w*",
    r"strip[ -_]*tease",
    r"jerk\w*[ -_]*off\w*",
    # --- Stronger sexual terms (plain word patterns; \\b added automatically) ---
    "twat",
    "minge",
    "prick",
    "knob",
    "wank",
    "wanker",
    "wanking",
    "titty",
    "slut",
    "slag",
    "skank",
    "slapper",
    "dildo",
    "vibrator",
    "handjob",
    "blowjob",
    "rimjob",
    "cum",
    "jizz",
    "semen",
    "spunk",
    "orgasm",
    "clit",
    "clitoris",
    "vagina",
    "pussies",
    "penis",
    "testicle",
    "scrotum",
    "anal",
    "anus",
    "butthole",
    "arse",
    "ballache",
    "sperm",
    # --- Sexual slang/acts observed in chat ---
    "masochist",
    r"perv\w*",
    r"spank\w*",
    r"nud(?:e\w*|ity|ist)",
    "edging",
    r"femboy\w*",
    "thicc",
    "wtaf",
    "wtf",
    "dafuq",
    "omfg",
    "grindr",
    "kurwa",
    "mpreg",
    "moaning",
    r"horn[yi]\w*",
    "erotic",
    "shag",
    "booty",
    r"twerk\w*",
    "noods",
    r"thirst\w*",
    "jugs",
    "safeword",
    r"stripper\w*",
    "cuck",
    r"pegg(?:ed|ing|er|ers)",
    "fingering",
    r"quick(?:ie|y)",
    r"undress\w*",
    "shibari",
    "milf",
    "moistness",
    r"fetish\w*",
    r"kink\w*",
]

_cache: dict[int, set[str]] = {}


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
