"""Tests for webapp.app: route registration and the legacy static pages."""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from webapp import app as app_module


def _app() -> web.Application:
    application = app_module.create_app()
    return application


async def test_legacy_pages_are_served() -> None:
    async with TestClient(TestServer(_app())) as client:
        for path in ("/go.html", "/tictactoe.html", "/legacy/", "/legacy/index.html", "/legacy/go.html"):
            response = await client.get(path)
            assert response.status == 200, path
            assert response.content_type == "text/html", path


async def test_legacy_page_content_is_the_real_file() -> None:
    async with TestClient(TestServer(_app())) as client:
        response = await client.get("/go.html")
        body = await response.text()
        assert "<html" in body.lower()


async def test_index_is_the_webapp_not_the_launcher() -> None:
    """The legacy launcher must not take over the site root."""
    async with TestClient(TestServer(_app())) as client:
        response = await client.get("/")
        assert response.status == 200
        body = await response.text()
        assert "Clockwork" in body
        assert "Local Games Launcher" not in body


async def test_legacy_pages_do_not_require_a_session() -> None:
    """Legacy pages are public, so auth must not be configured for them to render."""
    async with TestClient(TestServer(_app())) as client:
        for path in ("/go.html", "/tictactoe.html", "/legacy/", "/legacy/index.html"):
            response = await client.get(path)
            assert response.status == 200, path


def test_legacy_files_exist_on_disk() -> None:
    for name in ("go.html", "tictactoe.html", "index.html"):
        assert (app_module.LEGACY_DIR / name).is_file(), name


def test_legacy_routes_do_not_take_user_input() -> None:
    """Only fixed routes exist, so no request can influence the filename served."""
    assert set(app_module.LEGACY_PAGES) == {"/go.html", "/tictactoe.html", "/legacy/"}
    assert set(app_module.LEGACY_PAGES.values()) == {"go.html", "tictactoe.html", "index.html"}
    assert set(app_module.LEGACY_PAGES.values()) <= {
        path.name for path in app_module.LEGACY_DIR.iterdir()
    }


@pytest.mark.parametrize("path", ["/go.html/../shop.py", "/legacy/../../etc/passwd"])
def test_no_traversal_paths_are_registered(path: str) -> None:
    routes = {getattr(route, "canonical", None) for route in _app().router.routes()}
    assert path not in routes
