"""Aggregates gig sources with a per-source TTL cache and stale-on-error fallback."""

import time

import aiohttp

from .models import Gig, GigSearch, SourceError, SourceResult
from .sources.base import GigSource
from .sources.skiddle import SkiddleSource

CACHE_TTL_SECONDS = 600


class GigService:
    def __init__(self, sources: list[GigSource] | None = None) -> None:
        self._sources: list[GigSource] = sources if sources is not None else [SkiddleSource()]
        self._cache: dict[tuple[str, str], tuple[float, tuple[Gig, ...]]] = {}

    @property
    def sources(self) -> list[GigSource]:
        return self._sources

    async def search(self, http: aiohttp.ClientSession, query: GigSearch) -> list[SourceResult]:
        return [await self._search_source(source, http, query) for source in self._sources]

    async def _search_source(
        self,
        source: GigSource,
        http: aiohttp.ClientSession,
        query: GigSearch,
    ) -> SourceResult:
        cache_key = (source.name, repr(query))
        now = time.monotonic()
        cached = self._cache.get(cache_key)

        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            return SourceResult(
                source=source.name,
                attribution=source.attribution,
                attribution_url=source.attribution_url,
                gigs=cached[1],
            )

        try:
            gigs = tuple(await source.search(http, query))
        except SourceError as exc:
            if cached is not None:
                return SourceResult(
                    source=source.name,
                    attribution=source.attribution,
                    attribution_url=source.attribution_url,
                    gigs=cached[1],
                    stale=True,
                    error=str(exc),
                )
            return SourceResult(
                source=source.name,
                attribution=source.attribution,
                attribution_url=source.attribution_url,
                gigs=(),
                error=str(exc),
            )

        self._cache[cache_key] = (now, gigs)
        return SourceResult(
            source=source.name,
            attribution=source.attribution,
            attribution_url=source.attribution_url,
            gigs=gigs,
        )
