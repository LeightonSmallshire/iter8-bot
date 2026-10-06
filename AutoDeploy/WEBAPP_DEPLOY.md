# Webapp deployment

Server-side changes required to serve the webapp on `trejon.smallshire.co.uk`.
None of these are in the repo — they live on other machines.

## Where things actually live

Both changes below are **not** made on the Pi, and not in this repo:

| What | Where |
| --- | --- |
| Public nginx (`nginx-proxy`) | compose project `bitmmo-5`, from `/home/zero/CLionProjects/BitMMO-5/docker-compose.yml` on machine `zero` |
| Public nginx config | **baked into the `bitmmo-5-nginx-proxy` image** (`COPY ./config/ /etc/nginx/`) — not a bind mount |
| Shared env file | `/app/.env`, **baked into the `autodeploy-iter8-deployer` image**, built from `/home/zero/PycharmProjects/iter8-bot/AutoDeploy` on machine `zero` |

Do not edit `/home/pi/local-launch/nginx/nginx.conf` on the Pi. That is a different,
currently-down stack (`nginx:latest` + authelia/code-server/portainer) whose conf is
bind-mounted but is a different, older file. It does not affect the running proxy.

Patching the running container with `docker exec` works until the proxy is next rebuilt,
then the change is silently lost.

## Request path

```
browser
  → https://trejon.smallshire.co.uk/<path>          TLS terminated upstream (Let's Encrypt)
  → 67.208.54.158 → Pi:8080                         plain HTTP to the nginx-proxy container
  → http://bot-web-server:80/<path>                 internal proxy, bot-web-server container
  → http://iter8-bot-runner:8090/<path>              aiohttp webapp inside the bot
```

TLS is terminated **upstream** of the Pi. The proxy's `listen 443` is plain HTTP behind a
forwarder, and its config has no `ssl_certificate` at all. That is fine: the webapp only
needs `WEBAPP_BASE_URL` to be the public `https://` origin, which is what makes session
cookies `Secure` and satisfies Discord's redirect-URI rule.

`bot-web-server` (`Web/config/nginx.conf`) is an nginx container in the same compose
project as the bot. It exists purely so the host nginx has a stable upstream to point
at; it serves the legacy static pages at `/go.html`, `/tictactoe.html` and `/legacy/`,
and proxies everything else to the bot. It re-resolves DNS per request
(`resolver 127.0.0.11`) so it survives the bot container getting a new IP on each deploy.

The bot is **not** published to the host. Nothing but the host nginx can reach it.

## 1. Public nginx

The webapp generates root-absolute URLs (`/static/…`, `/shop`, `/api/…`, `/auth/…`), so it
needs to be served from `/`, not from a path prefix. Add to the `server` block for
`trejon.smallshire.co.uk` in the BitMMO-5 nginx config on machine `zero`:

```nginx
location / {
    proxy_pass http://botweb_backend/;
    proxy_buffering off;
}
```

Then rebuild/recreate the proxy. Because the config is baked into the image, either rebuild
`bitmmo-5-nginx-proxy` or bind-mount a conf over `/etc/nginx/nginx.conf` — the bind mount
is the better long-term fix, and makes this file the one place the config lives.

Nginx matches the longest prefix, so the existing `/bot/`, `/botweb/`, `/scratch/` and
`/status` locations keep winning. `/botweb/` may be left in place as an alias entry point,
but `/` is canonical.

Side effect: paths that previously 404'd on the host now reach the bot and return the
webapp's 404. Add an explicit `location` block before adding anything else to that domain.

Verify with `nginx -t` before reloading.

## 2. Environment

The bot reads `env_file: ../.env`, resolved from `repo/docker-compose.yml` to `/app/.env`,
which is the same file the deployer passes as `--env-file ./.env`. That file is baked into
the deployer image, so adding vars means editing it at
`/home/zero/PycharmProjects/iter8-bot/AutoDeploy` on machine `zero` and rebuilding
`autodeploy-iter8-deployer` — or, better, bind-mount a host `.env` to `/app/.env` so later
changes do not need an image rebuild.

Current keys, as deployed: `MODE` (`Live`), `DISCORD_TOKEN`, `TENOR_TOKEN`,
`OPENROUTER_API_KEY`, `LOGFIRE_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `MEM0_API_KEY`,
`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `DISCORD_WEBHOOK_ID`, `DISCORD_WEBHOOK_TOKEN`,
`WEBHOOK_SECRET`. None of the webapp keys are present yet. Add:

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

The public nginx container sits on **two** networks and needs both:

| Network | Needed for |
| --- | --- |
| `iter8-network` | `bot-web-server:80` — external network declared in `docker-compose.yml` |
| `autodeploy_default` | `iter8-deployer:8080` — the `/bot/` webhook upstream |

`iter8-bot-runner` and `bot-web-server` are on `iter8-network`; `iter8-deployer` is on
`autodeploy_default` only. Verified live on the Pi.

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

Note `/bot/` itself returns 404 — the deployer only serves `/webhook` and `/restart`, so
`/bot/` hitting nothing is expected, not a fault.

## Notes

- `--remove-orphans` in `AutoDeploy/update.sh` deletes containers for services no longer in
  the compose file. `bot-web-server` is in the compose file, so it is recreated in place and
  the upstream keeps resolving across deploys. It is scoped to the `autorun-iter8-bot`
  project, so the public proxy is untouched by a deploy.
- `AutoDeploy/update.sh` runs `git reset --hard origin/main`, so only committed work on
  `main` is deployed. It does not `git clean`, so untracked files in the clone persist.
- The deployer runs `update.sh` on its own startup as well as on each push to `main`, so
  restarting it also triggers a deploy. `GET /restart` (behind `/bot/restart`) re-runs it.
- The deployer image is Python 3.14; the bot image is Python 3.11. Both fine as-is.