# AGENTS.md

## Project

Discord bot (`Python/`). The C++ bot in `Cpp/` is a legacy/alternate implementation and is NOT the deployed runner.

## Commands (run from repo root)

Linting, typechecking, and tests all run inside `Python/`.

```bash
# Full suite (mypy + ruff + pytest, results written to temp/)
python run_tests.py

# Individual checks — run from Python/ directory
cd Python
python -m ruff check .
python -m mypy --show-error-codes --strict .
python -m pytest --tb=short

# Single test
python -m pytest tests/test_tools.py::test_function_name -v
```

The webapp's Activity bootstrap also has JavaScript tests. There is no JS build step, so
these run on the bundled Node's test runner, from the repo root:

```bash
node --test "Python/webapp/static/*.test.mjs"
```

Two pre-existing suite quirks worth knowing:

- `tests/test_startup.py` boots the real bot, so it needs port `8090` free. Stop the dev
  bot first or it fails with `winerror 10048`.
- `tests/test_tools.py` has a broken `BaseDeps` import and must be ignored
  (`--ignore=tests/test_tools.py`); everything else passes.

Recommended order: `ruff → mypy → pytest`.

## Linting

- **Ruff**: target py312, line-length 120. Selects E, W, F, I, N, UP, B, SIM. E501 is ignored (handled by formatter); N999 is ignored (parent folder is named "Python"). isort `known-first-party = ["cogs"]`.
- **Mypy**: strict mode (`--strict`), `ignore_missing_imports = true`.

## Architecture

- **Entrypoint**: `Python/entrypoint.py` — loads env files (`data/.env`, `../AutoDeploy/.env`, local), configures Logfire, then calls `main.main()`.
- **Bot**: `HotReloadBot` in `Python/main.py` — command prefix `!`, all intents. Picks `DISCORD_TOKEN_LIVE` vs `DISCORD_TOKEN_DEV` from `MODE` env.
- **Webapp**: `Python/webapp/` — aiohttp.web served by the bot on port `8090` (`WEBAPP_PORT`); hosts `/shop`, `/credits`, `/gigs` behind Discord OAuth2, plus the legacy static pages at `/go.html`, `/tictactoe.html` and `/legacy/`. Requires env: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `WEBAPP_BASE_URL` (public origin, redirect URI is `{base}/auth/callback`), `WEBAPP_SESSION_SECRET`; optional: `SHOP_ANNOUNCE_CHANNEL_ID` (defaults to channel named `general-idiocy`), `SKIDDLE_API_KEY` (gig search; unauthenticated shows a config error until set). The port is not published to the host: the public reverse proxy reaches it over the `iter8-network` docker network as `iter8-bot-runner:8090`.
- **Discord Activity**: the site root doubles as the Activity entry point. Discord proxies it through `<application id>.discordsays.com` and frames it inside `discord.com`, so `Python/webapp/static/activity.js` detects the frame and signs in via the vendored Embedded App SDK (`static/vendor/discordSdk.js`, named export) instead of the redirect flow, which Discord refuses to have framed. **SDK v2, per the [Embedded App SDK reference](https://docs.discord.com/developers/developer-tools/embedded-app-sdk):** the command is `sdk.commands.authorize(...)`, whose `AuthorizeRequest` **requires `client_id`** and takes scopes in a **singular `scope` array**; it resolves to `{ code }`. `authenticate` is the opposite direction — it accepts an *existing* `access_token` and will not mint one. Neither command exists on the SDK instance itself. `POST /auth/exchange` takes `{"code": …}` and trades it at the token endpoint with `redirect_uri` = `AuthConfig.activity_redirect_uri` (the registered Activity URL, defaulting to `WEBAPP_BASE_URL`). Failures surface Discord's own `error_description`, and a non-JSON body is reported as a likely CDN block — the OAuth session **must** send a browser `User-Agent` (`DISCORD_USER_AGENT`), because Discord's CDN answers aiohttp's default with `403 / error code 1010`. Because the exchange is made from inside the frame, the cookie lands on Discord's proxy host, which is also why session cookies become `SameSite=None; Secure` over https (`AuthConfig.same_site`). See `AutoDeploy/WEBAPP_DEPLOY.md` for the portal prerequisite.
- **Cogs**: `Python/cogs/` — auto-discovered and hot-reloaded on startup; any new `.py` file placed there is loaded automatically (no registration step).
- **LangGraph agent**: `Python/cogs/agent_elmo/` — state machine (`think → agent → tools → loop → end`) using OpenRouter via `ChatOpenAI`, SQLite checkpointing (`data/agent_storage.db`), and a sandbox abstraction supporting both Docker and Modal backends. See `agent_v2_plan.md` for design.
- **DB**: SQLite via aiosqlite. Persistent Docker volume `iter8-bot-data` mounted at `/app/data` (must be created separately as an external volume).
- **Deploy**: no GitHub Actions. A custom FastAPI webhook server (`AutoDeploy/deployer.py`) triggers `docker compose up --build --force-recreate -d` on `main` pushes.

## Conventions

- Target Python 3.12. Uses discord.py 2.7.1, LangGraph 1.2.4.
- Pytest uses `asyncio_mode = "auto"` — do NOT add `@pytest.mark.asyncio`.
- Secrets are external/env-provided (see `stack.env`, `../.env`, `data/.env`); never commit env files.
