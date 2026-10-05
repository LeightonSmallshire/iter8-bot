"""Skiddle events source (https://www.skiddle.com/api/, non-commercial API)."""

import os

import aiohttp

from ..models import Gig, GigSearch, SourceError

API_URL = "https://www.skiddle.com/api/v1/events/search/"


class SkiddleSource:
    name = "Skiddle"
    attribution = "Event data provided by Skiddle (non-commercial API)"
    attribution_url = "https://www.skiddle.com/api"

    def __init__(self) -> None:
        self._key = os.environ.get("SKIDDLE_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _params(self, query: GigSearch) -> dict[str, str]:
        params: dict[str, str] = {"api_key": self._key, "description": "1"}
        if query.latitude is not None and query.longitude is not None:
            params["latitude"] = str(query.latitude)
            params["longitude"] = str(query.longitude)
            params["radius"] = str(query.radius)
            params["order"] = "distance"
        else:
            params["country"] = query.country
            params["order"] = "date"
        if query.keyword:
            params["keyword"] = query.keyword
        if query.category:
            params["eventcode"] = query.category.upper()
        if query.min_date:
            params["minDate"] = query.min_date
        if query.max_date:
            params["maxDate"] = query.max_date
        params["limit"] = str(query.limit)
        params["offset"] = str(query.offset)
        return params

    async def search(self, http: aiohttp.ClientSession, query: GigSearch) -> list[Gig]:
        if not self.configured:
            raise SourceError("Skiddle API key is not configured.")

        try:
            async with http.get(
                API_URL,
                params=self._params(query),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                payload: object = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SourceError("Could not reach Skiddle.") from exc

        if response.status == 403 or response.status == 429:
            raise SourceError("Skiddle rejected the request (rate limit or invalid API key).")
        if response.status != 200:
            detail = _error_detail(payload)
            raise SourceError(detail or f"Skiddle returned HTTP {response.status}.")

        return parse(payload)


def _error_detail(payload: object) -> str | None:
    if isinstance(payload, dict):
        message = payload.get("errormessage")
        if isinstance(message, str) and message:
            return message
    return None


def parse(payload: object) -> list[Gig]:
    """Map a Skiddle response to gigs; tolerant of documented shape drift."""
    if not isinstance(payload, dict):
        raise SourceError("Unexpected Skiddle response.")

    results = payload.get("results")
    if isinstance(results, dict):
        events = results.get("events")
    elif isinstance(results, list):
        events = results
    else:
        raise SourceError("Unexpected Skiddle response.")

    if not isinstance(events, list):
        return []

    gigs: list[Gig] = []
    for raw in events:
        gig = _parse_event(raw)
        if gig is not None:
            gigs.append(gig)
    return gigs


def _parse_event(raw: object) -> Gig | None:
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("eventname") or raw.get("name") or "").strip()
    if not title:
        return None

    if _is_cancelled(raw.get("cancelled")):
        return None

    venue_raw = raw.get("venue")
    venue = venue_raw.get("name", "") if isinstance(venue_raw, dict) else ""
    town = venue_raw.get("town", "") if isinstance(venue_raw, dict) else ""

    event_id = raw.get("eventcode") or raw.get("id") or ""
    url = str(raw.get("link") or "").strip()
    if not url and event_id:
        url = f"https://www.skiddle.com/{event_id}/"

    return Gig(
        title=title,
        date=_parse_date(raw),
        start_time=_parse_start_time(raw),
        venue=str(venue or ""),
        town=str(town or ""),
        url=url,
        price=_format_price(raw),
        source=SkiddleSource.name,
        artists=_parse_artists(raw.get("artists")),
        image_url=_parse_image(raw),
        category=_parse_category(raw),
    )


def _parse_image(raw: dict[str, object]) -> str:
    """Prefer the ~8KB large artwork over the thumbnail and the ~100KB xlarge."""
    for field in ("largeimageurl", "imageurl", "xlargeimageurl"):
        value = str(raw.get(field) or "").strip()
        if not value.startswith(("http://", "https://")):
            continue
        if "/assets/default" in value:
            continue
        return value
    return ""


def _parse_category(raw: dict[str, object]) -> str:
    genres = raw.get("genres")
    if not isinstance(genres, list):
        return ""
    for item in genres:
        name = _genre_name(item)
        if name:
            return name
    return ""


def _genre_name(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or "").strip()
    if isinstance(item, str):
        return item.strip()
    return ""


def _is_cancelled(value: object) -> bool:
    return value is True or value == 1 or value == "1"


def _parse_date(raw: dict[str, object]) -> str:
    date = str(raw.get("date") or "").strip()
    if date:
        return date
    startdate = str(raw.get("startdate") or "")
    return startdate[:10] if len(startdate) >= 10 else ""


def _parse_start_time(raw: dict[str, object]) -> str:
    start_time = str(raw.get("start_time") or "").strip()
    if start_time:
        return start_time
    startdate = str(raw.get("startdate") or "")
    if len(startdate) >= 16 and "T" in startdate:
        return startdate[11:16]
    opening = raw.get("openingtimes")
    if isinstance(opening, dict):
        doors = str(opening.get("doorsopen") or "")
        if doors:
            return doors
    return ""


def _format_price(raw: dict[str, object]) -> str:
    pricing = raw.get("ticketpricing")
    if isinstance(pricing, dict):
        low = _as_price(pricing.get("minPrice"))
        high = _as_price(pricing.get("maxPrice"))
        if low is not None or high is not None:
            return _price_range(low, high)
    low = _as_price(raw.get("min_price"))
    high = _as_price(raw.get("max_price"))
    if low is None and high is None:
        low = _as_price(raw.get("entryprice"))
    return _price_range(low, high)


def _price_range(low: float | None, high: float | None) -> str:
    if low is None and high is None:
        return ""
    if low is None:
        low = high
    if high is None:
        high = low
    assert low is not None and high is not None
    if low == 0 and high == 0:
        return "Free"
    if low == high:
        return f"£{low:g}"
    return f"£{low:g}–£{high:g}"


def _as_price(value: object) -> float | None:
    if value is None or value is False:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _parse_artists(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, list):
        return tuple(name for item in value if (name := _artist_name(item)))
    if isinstance(value, dict):
        return tuple(name for item in value.values() if (name := _artist_name(item)))
    return ()


def _artist_name(item: object) -> str | None:
    if isinstance(item, str):
        return item if item.strip() else None
    if isinstance(item, dict):
        name = str(item.get("name") or "").strip()
        return name or None
    text = str(item).strip()
    return text or None
