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

Recommended order: `ruff → mypy → pytest`.

## Linting

- **Ruff**: target py312, line-length 120. Selects E, W, F, I, N, UP, B, SIM. E501 is ignored (handled by formatter); N999 is ignored (parent folder is named "Python"). isort `known-first-party = ["cogs"]`.
- **Mypy**: strict mode (`--strict`), `ignore_missing_imports = true`.

## Architecture

- **Entrypoint**: `Python/entrypoint.py` — loads env files (`data/.env`, `../AutoDeploy/.env`, local), configures Logfire, then calls `main.main()`.
- **Bot**: `HotReloadBot` in `Python/main.py` — command prefix `!`, all intents. Picks `DISCORD_TOKEN_LIVE` vs `DISCORD_TOKEN_DEV` from `MODE` env.
- **Webapp**: `Python/webapp/` — aiohttp.web served by the bot on port `8090` (`WEBAPP_PORT`); hosts `/shop`, `/credits`, `/gigs` behind Discord OAuth2. Requires env: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `WEBAPP_BASE_URL` (public origin, redirect URI is `{base}/auth/callback`), `WEBAPP_SESSION_SECRET`; optional: `SHOP_ANNOUNCE_CHANNEL_ID` (defaults to channel named `general-idiocy`), `SKIDDLE_API_KEY` (gig search; unauthenticated shows a config error until set). The old `Web/` container was removed from docker-compose; files are kept on disk for reference only.
- **Cogs**: `Python/cogs/` — auto-discovered and hot-reloaded on startup; any new `.py` file placed there is loaded automatically (no registration step).
- **LangGraph agent**: `Python/cogs/agent_elmo/` — state machine (`think → agent → tools → loop → end`) using OpenRouter via `ChatOpenAI`, SQLite checkpointing (`data/agent_storage.db`), and a sandbox abstraction supporting both Docker and Modal backends. See `agent_v2_plan.md` for design.
- **DB**: SQLite via aiosqlite. Persistent Docker volume `iter8-bot-data` mounted at `/app/data` (must be created separately as an external volume).
- **Deploy**: no GitHub Actions. A custom FastAPI webhook server (`AutoDeploy/deployer.py`) triggers `docker compose up --build --force-recreate -d` on `main` pushes.

## Conventions

- Target Python 3.12. Uses discord.py 2.7.1, LangGraph 1.2.4.
- Pytest uses `asyncio_mode = "auto"` — do NOT add `@pytest.mark.asyncio`.
- Secrets are external/env-provided (see `stack.env`, `../.env`, `data/.env`); never commit env files.
