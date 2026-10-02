"""Gig search models shared across sources and the web layer."""

from dataclasses import dataclass

LOCATIONS: dict[str, tuple[float, float]] = {
    "Manchester": (53.4839, -2.2446),
    "London": (51.5074, -0.1278),
    "Leeds": (53.8008, -1.5491),
    "Liverpool": (53.4084, -2.9916),
    "Birmingham": (52.4862, -1.8904),
    "Sheffield": (53.3811, -1.4701),
    "Newcastle": (54.9783, -1.6178),
    "Bristol": (51.4545, -2.5879),
    "Cardiff": (51.4816, -3.1791),
    "Glasgow": (55.8642, -4.2515),
    "Edinburgh": (55.9533, -3.1883),
    "Nottingham": (52.9548, -1.1581),
    "Brighton": (50.8225, -0.1372),
    "Oxford": (51.7520, -1.2577),
    "Cambridge": (52.2053, 0.1218),
}

CATEGORIES: dict[str, str] = {
    "LIVE": "Live music",
    "CLUB": "Clubbing / dance",
    "FEST": "Festivals",
    "COMEDY": "Comedy",
    "THEATRE": "Theatre / dance",
    "EXHIB": "Exhibitions",
    "KIDS": "Kids / family",
    "SPORT": "Sport",
    "ARTS": "The arts",
    "BARPUB": "Bar / pub",
}


class SourceError(Exception):
    """A gig source failed; message is safe to show the user."""


@dataclass(frozen=True)
class Gig:
    title: str
    date: str
    start_time: str
    venue: str
    town: str
    url: str
    price: str
    source: str
    artists: tuple[str, ...] = ()
    image_url: str = ""
    category: str = ""


@dataclass(frozen=True)
class GigSearch:
    keyword: str = ""
    latitude: float | None = None
    longitude: float | None = None
    radius: int = 10
    country: str = "GB"
    category: str | None = None
    min_date: str | None = None
    max_date: str | None = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class SourceResult:
    source: str
    attribution: str
    attribution_url: str
    gigs: tuple[Gig, ...]
    stale: bool = False
    error: str | None = None
