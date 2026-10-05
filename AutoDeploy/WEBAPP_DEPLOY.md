# Webapp deployment

Server-side changes required to serve the webapp on `trejon.smallshire.co.uk`.
None of these are in the repo — they live on the host.

## Request path

```
browser
  → https://trejon.smallshire.co.uk/<path>          host nginx (443, TLS terminated here)
  → http://bot-web-server:80/<path>                internal proxy, bot-web-server container
  → http://iter8-bot-runner:8090/<path>             aiohttp webapp inside the bot
```

`bot-web-server` (`Web/config/nginx.conf`) is an nginx container in the same compose
project as the bot. It exists purely so the host nginx has a stable upstream to point
at; it serves the legacy static pages at `/go.html`, `/tictactoe.html` and `/legacy/`,
and proxies everything else to the bot. It re-resolves DNS per request
(`resolver 127.0.0.11`) so it survives the bot container getting a new IP on each deploy.

The bot is **not** published to the host. Nothing but the host nginx can reach it.

## 1. Host nginx

The webapp generates root-absolute URLs (`/static/…`, `/shop`, `/api/…`, `/auth/…`), so it
needs to be served from `/`, not from a path prefix. Add to the `server` block for
`trejon.smallshire.co.uk`:

```nginx
location / {
    proxy_pass http://botweb_backend/;
    proxy_buffering off;
}
```

Nginx matches the longest prefix, so the existing `/bot/`, `/botweb/`, `/scratch/` and
`/status` locations keep winning. `/botweb/` may be left in place as an alias entry point,
but `/` is canonical.

Side effect: paths that previously 404'd on the host now reach the bot and return the
webapp's 404. Add an explicit `location` block before adding anything else to that domain.

Reload with `nginx -t && nginx -s reload`.

## 2. Environment

The bot reads `env_file: ../.env`, resolved from `repo/docker-compose.yml`, which is the
same file the deployer passes as `--env-file ./.env` — i.e. the host `.env` that already
holds `WEBHOOK_SECRET` and the Discord tokens. Add:

```dotenv
WEBAPP_BASE_URL=https://trejon.smallshire.co.uk
DISCORD_CLIENT_ID=<oauth2 application id>
DISCORD_CLIENT_SECRET=<oauth2 client secret>
WEBAPP_SESSION_SECRET=<long random string>
SKIDDLE_API_KEY=<skiddle key>          # optional; gigs show a config error without it
SHOP_ANNOUNCE_CHANNEL_ID=<channel id>  # optional; defaults to channel named general-idiocy
```

`WEBAPP_BASE_URL` must be the public https origin. It drives the OAuth redirect URI and
makes session cookies `Secure`; the bot→proxy hop stays plain http.

If any of `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `WEBAPP_BASE_URL` or
`WEBAPP_SESSION_SECRET` is missing, the bot still boots but `/` and every `/api/*` redirect
to `/auth/login`, which returns 503.

## 3. Discord application

Register the redirect URI, exactly:

```
https://trejon.smallshire.co.uk/auth/callback
```

Discord rejects non-https redirect URIs (except `localhost`), and the value must match
byte for byte.

## 4. Docker network

The host nginx must be attached to `iter8-network`, the same external network declared in
`docker-compose.yml`, or the `bot-web-server:80` and `iter8-deployer:8080` upstreams will
not resolve.

## 5. Verify after deploy

```bash
curl -sI https://trejon.smallshire.co.uk/healthz          # {"status":"ok"}
curl -s  https://trejon.smallshire.co.uk/                  # login page
curl -sI https://trejon.smallshire.co.uk/static/shop.css   # 200, text/css
curl -sI https://trejon.smallshire.co.uk/go.html           # legacy page still served
curl -sI https://trejon.smallshire.co.uk/bot/webhook      # deployer still reachable
```

Then log in through Discord and confirm `/shop`, `/credits` and `/gigs` load, and that
`/gigs` returns results rather than a Skiddle config error.

Check the bot log for `Webapp listening on 0.0.0.0:8090` and, if auth env is missing,
`Webapp auth not configured`.

## Notes

- `--remove-orphans` in `AutoDeploy/update.sh` deletes containers for services no longer in
  the compose file. `bot-web-server` is in the compose file, so it is recreated in place and
  the upstream keeps resolving across deploys.
- `AutoDeploy/update.sh` runs `git reset --hard origin/main`, so only committed work on
  `main` is deployed.
- The deployer runs `update.sh` on its own startup as well as on each push to `main`, so
  restarting it also triggers a deploy. `GET /restart` (behind `/bot/restart`) re-runs it.