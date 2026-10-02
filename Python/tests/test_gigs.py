"""Tests for the gigs feature: Skiddle parsing, query validation, and the aggregator cache."""

import time

import aiohttp
import pytest

import webapp.gigs.service as service_mod
from webapp.gigs import Gig, GigSearch, GigService, SourceError
from webapp.gigs.models import LOCATIONS
from webapp.gigs.routes import QueryError, parse_search
from webapp.gigs.sources.base import GigSource
from webapp.gigs.sources.skiddle import parse


def _live_event() -> dict[str, object]:
    """Event exactly as returned by the live Skiddle API (verified 2026-10-02)."""
    return {
        "EventCode": "LIVE",
        "eventcode": None,
        "id": "42618901",
        "eventname": "M&P's Jazz Brunch",
        "date": "2026-10-03",
        "startdate": "2026-10-03T13:00:00+00:00",
        "start_time": None,
        "openingtimes": {"doorsopen": "13:00", "doorsclose": "16:00", "lastentry": "13:30"},
        "entryprice": "",
        "ticketpricing": {"minPrice": 5, "maxPrice": 7},
        "min_price": None,
        "max_price": None,
        "link": "https://www.skiddle.com/whats-on/Manchester/Matt-And-Phreds/MPs-Jazz-Brunch/42618901/",
        "cancelled": "0",
        "venue": {"name": "Matt And Phreds", "town": "Manchester"},
        "artists": [
            {"artistid": "123559625", "name": "Harry Cambridge", "image": "https://example.com/a.jpg"},
        ],
    }


def _live_payload() -> dict[str, object]:
    free = _live_event()
    free["eventname"] = "Free Gig"
    free["ticketpricing"] = {"minPrice": 0, "maxPrice": 0}
    free["artists"] = []
    cancelled = _live_event()
    cancelled["eventname"] = "Cancelled Gig"
    cancelled["cancelled"] = "1"
    return {"error": 1, "totalcount": 3, "pagecount": 1, "results": [_live_event(), free, cancelled, "junk"]}


def test_parse_live_payload() -> None:
    gigs = parse(_live_payload())
    assert len(gigs) == 2
    gig = gigs[0]
    assert gig.title == "M&P's Jazz Brunch"
    assert gig.date == "2026-10-03"
    assert gig.start_time == "13:00"
    assert gig.venue == "Matt And Phreds"
    assert gig.town == "Manchester"
    assert gig.url.startswith("https://www.skiddle.com/whats-on/")
    assert gig.price == "£5–£7"
    assert gig.artists == ("Harry Cambridge",)
    assert gig.source == "Skiddle"


def test_parse_free_and_cancelled() -> None:
    gigs = parse(_live_payload())
    assert gigs[1].title == "Free Gig"
    assert gigs[1].price == "Free"
    assert all(g.title != "Cancelled Gig" for g in gigs)


def test_parse_single_price() -> None:
    payload: dict[str, object] = {"results": [{"eventname": "Solo", "ticketpricing": {"minPrice": 19, "maxPrice": 19}}]}
    assert parse(payload)[0].price == "£19"


def test_parse_documented_shape_still_works() -> None:
    payload: dict[str, object] = {
        "success": 1,
        "results": {
            "count": 1,
            "events": [
                {
                    "eventcode": "123",
                    "eventname": "Jazz Night",
                    "date": "2026-10-05",
                    "start_time": "20:00:00",
                    "venue": {"name": "The Forge", "town": "Manchester"},
                    "min_price": "10.00",
                    "max_price": "12.50",
                    "artists": {"1": "Alice", "2": "Bob"},
                },
            ],
        },
    }
    gig = parse(payload)[0]
    assert gig.url == "https://www.skiddle.com/123/"
    assert gig.start_time == "20:00:00"
    assert gig.price == "£10–£12.5"
    assert gig.artists == ("Alice", "Bob")


def test_parse_entryprice_fallback() -> None:
    payload: dict[str, object] = {"results": [{"eventname": "X", "entryprice": "5.00"}]}
    assert parse(payload)[0].price == "£5"


def test_parse_start_time_falls_back_to_doors_open() -> None:
    payload: dict[str, object] = {
        "results": [{"eventname": "X", "date": "2026-10-05", "openingtimes": {"doorsopen": "19:00"}}],
    }
    assert parse(payload)[0].start_time == "19:00"


def test_parse_date_falls_back_to_startdate() -> None:
    payload: dict[str, object] = {"results": [{"eventname": "X", "startdate": "2026-11-01T21:30:00+00:00"}]}
    gig = parse(payload)[0]
    assert gig.date == "2026-11-01"
    assert gig.start_time == "21:30"


def test_parse_artists_variants() -> None:
    as_strings: dict[str, object] = {"results": [{"eventname": "A", "artists": ["Zed", "  "]}]}
    assert parse(as_strings)[0].artists == ("Zed",)
    as_dicts: dict[str, object] = {"results": [{"eventname": "A", "artists": {"1": {"name": "Ann"}}}]}
    assert parse(as_dicts)[0].artists == ("Ann",)


def test_parse_skips_empty_title_and_junk() -> None:
    payload: dict[str, object] = {"results": [{"eventname": ""}, "junk", {"eventname": "Kept"}]}
    assert [g.title for g in parse(payload)] == ["Kept"]


def test_parse_rejects_bad_payload() -> None:
    payloads: list[object] = ["string", [], {}, {"nope": 1}]
    for bad in payloads:
        with pytest.raises(SourceError):
            parse(bad)
    assert parse({"results": {"events": "not-a-list"}}) == []


def test_parse_search_valid() -> None:
    query = parse_search({
        "keyword": "  jazz  ",
        "location": "Manchester",
        "radius": "25",
        "category": "live",
        "from": "2026-10-01",
        "to": "2026-10-07",
        "limit": "5",
    })
    assert query.keyword == "jazz"
    assert query.latitude == LOCATIONS["Manchester"][0]
    assert query.longitude == LOCATIONS["Manchester"][1]
    assert query.radius == 25
    assert query.category == "LIVE"
    assert query.min_date == "2026-10-01"
    assert query.max_date == "2026-10-07"
    assert query.limit == 5


def test_parse_search_defaults_without_location() -> None:
    query = parse_search({})
    assert query.latitude is None
    assert query.country == "GB"
    assert query.radius == 10
    assert query.category is None


def test_parse_search_rejects_bad_queries() -> None:
    cases = [
        ({"keyword": "x" * 121}, "120 characters"),
        ({"location": "Atlantis"}, "Unknown location."),
        ({"category": "NOPE"}, "Unknown category."),
        ({"from": "banana"}, "YYYY-MM-DD"),
        ({"from": "2026-10-10", "to": "2026-10-01"}, "must not be after"),
        ({"location": "Manchester", "radius": "999"}, "between 1 and 100"),
        ({"limit": "0"}, "between 1 and 100"),
        ({"offset": "-1"}, "between 0 and 10000"),
    ]
    for args, message in cases:
        with pytest.raises(QueryError, match=message):
            parse_search(args)


class FakeSource:
    name = "Fake"
    attribution = "Fake data"
    attribution_url = "https://example.com"

    def __init__(self, fail: str | None = None) -> None:
        self.calls = 0
        self.fail = fail

    async def search(self, http: aiohttp.ClientSession, query: GigSearch) -> list[Gig]:
        del http, query
        self.calls += 1
        if self.fail is not None:
            raise SourceError(self.fail)
        return [
            Gig(
                title=f"gig-{self.calls}",
                date="2026-10-05",
                start_time="",
                venue="",
                town="",
                url="",
                price="",
                source=self.name,
            )
        ]


def _service(source: FakeSource) -> GigService:
    sources: list[GigSource] = [source]
    return GigService(sources)


async def test_service_caches_fresh_results() -> None:
    source = FakeSource()
    service = _service(source)
    async with aiohttp.ClientSession() as http:
        first = await service.search(http, GigSearch(keyword="jazz"))
        second = await service.search(http, GigSearch(keyword="jazz"))
    assert source.calls == 1
    assert first[0].gigs == second[0].gigs
    assert not first[0].stale
    assert first[0].error is None


async def test_service_refetches_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeSource()
    service = _service(source)
    monkeypatch.setattr(service_mod, "CACHE_TTL_SECONDS", 0)
    async with aiohttp.ClientSession() as http:
        await service.search(http, GigSearch(keyword="jazz"))
        await service.search(http, GigSearch(keyword="jazz"))
    assert source.calls == 2


async def test_service_uses_stale_cache_on_error() -> None:
    source = FakeSource(fail="rate limited")
    service = _service(source)
    query = GigSearch(keyword="jazz")
    seeded = (
        Gig(title="seeded", date="", start_time="", venue="", town="", url="", price="", source=source.name),
    )
    service._cache[(source.name, repr(query))] = (time.monotonic() - 9999, seeded)
    async with aiohttp.ClientSession() as http:
        result = (await service.search(http, query))[0]
    assert result.stale
    assert result.error == "rate limited"
    assert result.gigs == seeded


async def test_service_error_without_cache_returns_empty() -> None:
    source = FakeSource(fail="rate limited")
    service = _service(source)
    async with aiohttp.ClientSession() as http:
        result = (await service.search(http, GigSearch(keyword="jazz")))[0]
    assert not result.stale
    assert result.error == "rate limited"
    assert result.gigs == ()
