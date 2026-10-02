"""Source interface: any gig provider that can run a GigSearch."""

from typing import Protocol

import aiohttp

from ..models import Gig, GigSearch


class GigSource(Protocol):
    name: str
    attribution: str
    attribution_url: str

    async def search(self, http: aiohttp.ClientSession, query: GigSearch) -> list[Gig]: ...
