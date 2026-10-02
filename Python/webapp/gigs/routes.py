"""Gig search page and JSON API."""

import datetime
import json
import time
from dataclasses import asdict
from typing import Any

import logfire
from aiohttp import web

from ..keys import HTTP_KEY
from . import CATEGORIES, LOCATIONS, GigSearch, GigService
from .models import SourceResult

GIGS_KEY: web.AppKey[GigService] = web.AppKey("gigs", GigService)

MAX_KEYWORD_LENGTH = 120


class QueryError(Exception):
    """Bad search query; message is safe to show the user."""


def parse_search(args: dict[str, str]) -> GigSearch:
    keyword = args.get("keyword", "").strip()
    if len(keyword) > MAX_KEYWORD_LENGTH:
        raise QueryError(f"Keyword must be {MAX_KEYWORD_LENGTH} characters or fewer.")

    latitude: float | None = None
    longitude: float | None = None
    radius = 10
    location = args.get("location", "").strip()
    if location:
        coords = LOCATIONS.get(location)
        if coords is None:
            raise QueryError("Unknown location.")
        latitude, longitude = coords
        radius = _int_arg(args, "radius", default=10, minimum=1, maximum=100)

    category = args.get("category", "").strip().upper()
    if category and category not in CATEGORIES:
        raise QueryError("Unknown category.")

    min_date = _date_arg(args, "from")
    max_date = _date_arg(args, "to")
    if min_date and max_date and min_date > max_date:
        raise QueryError("The 'from' date must not be after the 'to' date.")

    limit = _int_arg(args, "limit", default=20, minimum=1, maximum=100)
    offset = _int_arg(args, "offset", default=0, minimum=0, maximum=10_000)

    return GigSearch(
        keyword=keyword,
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        category=category or None,
        min_date=min_date,
        max_date=max_date,
        limit=limit,
        offset=offset,
    )


def _int_arg(args: dict[str, str], name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = args.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise QueryError(f"Invalid {name}.") from None
    if not minimum <= value <= maximum:
        raise QueryError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _date_arg(args: dict[str, str], name: str) -> str | None:
    raw = args.get(name, "").strip()
    if not raw:
        return None
    try:
        datetime.date.fromisoformat(raw)
    except ValueError:
        raise QueryError(f"Invalid {name} date; use YYYY-MM-DD.") from None
    return raw


def _results_payload(results: list[SourceResult]) -> list[dict[str, Any]]:
    payload = []
    for result in results:
        payload.append({
            "source": result.source,
            "attribution": result.attribution,
            "attribution_url": result.attribution_url,
            "stale": result.stale,
            "error": result.error,
            "gigs": [asdict(gig) for gig in result.gigs],
        })
    return payload


async def gigs_page(request: web.Request) -> web.StreamResponse:
    data = {
        "locations": list(LOCATIONS),
        "categories": [{"code": code, "label": label} for code, label in CATEGORIES.items()],
    }
    embedded = json.dumps(data).replace("<", "\\u003c")
    html = _GIGS_HTML.replace("__DATA__", embedded)
    return web.Response(text=html, content_type="text/html")


async def api_gigs(request: web.Request) -> web.StreamResponse:
    started = time.monotonic()
    try:
        query = parse_search(dict(request.query))
    except QueryError as exc:
        return web.json_response({"error": str(exc)}, status=400)

    service = request.app[GIGS_KEY]
    http = request.app[HTTP_KEY]
    results = await service.search(http, query)
    payload = _results_payload(results)

    errors = [f"{r.source}: {r.error}{' (stale)' if r.stale else ''}" for r in results if r.error]
    logfire.info(
        "gig search",
        keyword=query.keyword,
        near=f"{query.latitude:.4f},{query.longitude:.4f}" if query.latitude else "country-wide",
        radius=query.radius,
        category=query.category,
        window=f"{query.min_date or 'any'}..{query.max_date or 'any'}",
        gigs=sum(len(r["gigs"]) for r in payload),
        errors=errors or None,
        seconds=round(time.monotonic() - started, 2),
    )
    return web.json_response({"results": payload})


def register(app: web.Application) -> None:
    app[GIGS_KEY] = GigService()
    app.router.add_get("/gigs", gigs_page)
    app.router.add_get("/api/gigs", api_gigs)


_NAV = """<header><nav>
<a href="/shop">🛒 Shop</a>
<a href="/credits">💵 Credits</a>
<a href="/gigs" class="active">🎟️ Gigs</a>
<a href="/">Home</a>
<a href="/auth/logout" class="right">Log out</a>
</nav></header>"""

_GIGS_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gig Finder</title>
<link rel="stylesheet" href="/static/shop.css">
<link rel="stylesheet" href="/static/gigs.css">
</head>
<body>
{_NAV}
<main>
<h1>🎟️ Gig finder</h1>
<form id="search-form" class="search-form">
<div class="row">
<div class="field grow">
<label for="keyword">🔍 Keyword</label>
<input type="search" id="keyword" name="keyword" placeholder="artist, genre, venue…" maxlength="120" autocomplete="off">
</div>
<div class="field">
<label for="location">📍 Near</label>
<select id="location" name="location"></select>
</div>
<div class="field narrow">
<label for="radius">📏 Radius (mi)</label>
<input type="number" id="radius" name="radius" value="10" min="1" max="100" inputmode="numeric">
</div>
</div>
<div class="row">
<div class="field">
<label for="category">🎭 Category</label>
<select id="category" name="category"></select>
</div>
<div class="field">
<label for="from">📅 From</label>
<input type="date" id="from" name="from">
</div>
<div class="field">
<label for="to">📅 To</label>
<input type="date" id="to" name="to">
</div>
<div class="field">
<label for="sort">🔀 Sort</label>
<select id="sort">
<option value="date">Soonest first</option>
<option value="date-desc">Latest first</option>
<option value="title">Title A–Z</option>
<option value="price">Price: low → high</option>
</select>
</div>
<button type="submit" class="visually-hidden">Search</button>
</div>
</form>
<p id="search-status" class="status" role="status" aria-live="polite"></p>
<div id="notices" hidden></div>
<div id="results"></div>
<footer id="attribution" hidden></footer>
</main>
<script>window.GIGS = __DATA__;</script>
<script src="/static/gigs.js"></script>
</body>
</html>"""
