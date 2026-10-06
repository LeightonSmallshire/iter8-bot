# Webapp deployment

Server-side changes required to serve the webapp on `trejon.smallshire.co.uk`.
None of these are in the repo — they live on other machines.

## Where things actually live

Both changes below are **not** made on the Pi, and not in this repo:

| What | Where |
| --- | --- |
| Public nginx (`nginx-proxy`) | compose project `bitmmo-5`, from `/home/zero/CLionProjects/BitMMO-5/docker-compose.yml` on machine `zero` |
| Public nginx config | **baked into the `bitmmo-5-nginx-proxy` image** (`COPY ./config/ /etc/nginx/`) — not a bind mount |
| Shared env file | `/app/.env`, **baked into the `autodeploy-iter8-deployer` image** (root filesystem is read-only) |
| Webapp env file | `/app/data/webapp.env`, on the shared `iter8-bot-data` volume — writable, survives deploys |

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
  → http://iter8-bot-runner:8090/<path>              aiohttp webapp inside the bot
```

The bot serves everything itself, including the legacy static pages at `/go.html`,
`/tictactoe.html` and `/legacy/`. There is no intermediate proxy container: the
`bot-web-server` service was removed from `docker-compose.yml`, and the public proxy now
points straight at `iter8-bot-runner:8090`.

The bot is **not** published to the host. Nothing but the proxy can reach it, over the
`iter8-network` docker network.

TLS is terminated **upstream** of the Pi. The proxy's `listen 443` is plain HTTP behind a
forwarder, and its config has no `ssl_certificate` at all. That is fine: the webapp only
needs `WEBAPP_BASE_URL` to be the public `https://` origin, which is what makes session
cookies `Secure` and satisfies Discord's redirect-URI rule.

## 1. Public nginx

The webapp generates root-absolute URLs (`/static/…`, `/shop`, `/api/…`, `/auth/…`), so it
needs to be served from `/`, not from a path prefix. Two changes to the `server` block for
`trejon.smallshire.co.uk` in the BitMMO-5 nginx config on machine `zero`:

- point the `botweb_backend` upstream at `iter8-bot-runner:8090`
- add a `location /` that proxies to `botweb_backend`

```nginx
upstream botweb_backend {
    zone botweb_backend_zone 64k;
    server iter8-bot-runner:8090 resolve;
}

location / {
    proxy_pass http://botweb_backend/;
    proxy_buffering off;
}
```

A ready-made diff against the config as it is actually running is in
`AutoDeploy/patches/nginx-bitmmo-root-target.patch`; see `AutoDeploy/patches/README.md` for
how to apply it. Because the config is baked into the image, either rebuild
`bitmmo-5-nginx-proxy` or bind-mount a conf over `/etc/nginx/nginx.conf` — the bind mount
is the better long-term fix, and makes this repo's copy the source of truth.

Nginx matches the longest prefix, so the existing `/bot/`, `/botweb/`, `/scratch/` and
`/status` locations keep winning. `/botweb/` may be left in place as an alias entry point,
but `/` is canonical. `resolve` is already used in this config, so a new IP for the bot
container after a deploy is not a problem.

Side effect: paths that previously 404'd on the host now reach the bot and return the
webapp's 404. Add an explicit `location` block before adding anything else to that domain.

Verify with `nginx -t` before reloading.

## 2. Environment

The bot reads `env_file: ../.env` (resolved from `repo/docker-compose.yml` to
`/app/.env`) plus a second, optional `env_file` at `/app/data/webapp.env`. The first is
baked into the `autodeploy-iter8-deployer` image and that container's root filesystem is
read-only; the second lives on the shared `iter8-bot-data` volume, which compose resolves
inside the deployer container and which survives bot deploys and container recreation.

Current keys in `/app/.env`, as deployed: `MODE` (`Live`), `DISCORD_TOKEN`, `TENOR_TOKEN`,
`OPENROUTER_API_KEY`, `LOGFIRE_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `MEM0_API_KEY`,
`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `DISCORD_WEBHOOK_ID`, `DISCORD_WEBHOOK_TOKEN`,
`WEBHOOK_SECRET`. None of the webapp keys are present yet, so create
`/app/data/webapp.env` with:

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

## 4. Discord Activity

The site root is also the Discord Activity entry point. The Activity URL must be
registered in the developer portal for application `1425483577587531886`, under
**Activities**. Set it to the public origin:

```
https://trejon.smallshire.co.uk
```

Discord serves the Activity through `<application id>.discordsays.com`. If that hostname
has no provisioned origin — wrong URL, or none set — the frame fails with **HTTP 522**
(`server: cloudflare`, `retry-after`), which looks like our site being down but is not:
nothing reaches the Pi at all. Once the URL is registered it resolves and the frame loads.

The same URL is the `redirect_uri` presented when trading the SDK's authorization code, so
it must match byte for byte. Set `WEBAPP_ACTIVITY_URL` only if the Activity is registered
somewhere other than the public origin; otherwise it defaults to `WEBAPP_BASE_URL`.

Verify by loading the Activity in a real Discord client. This cannot be tested from a
script: Discord's authorize and RPC endpoints reject non-browser clients.

## 5. Docker network

The public nginx container sits on **two** networks and needs both:

| Network | Needed for |
| --- | --- |
| `iter8-network` | `iter8-bot-runner:8090` — external network declared in `docker-compose.yml` |
| `autodeploy_default` | `iter8-deployer:8080` — the `/bot/` webhook upstream |

`iter8-deployer` is on `autodeploy_default` only. Verified live on the Pi.

## 6. Verify after deploy

```bash
curl -sI https://trejon.smallshire.co.uk/healthz          # {"status":"ok"}
curl -s  https://trejon.smallshire.co.uk/                  # login page
curl -sI https://trejon.smallshire.co.uk/static/shop.css   # 200, text/css
curl -sI https://trejon.smallshire.co.uk/go.html           # legacy page still served
curl -sI https://trejon.smallshire.co.uk/legacy/           # legacy directory
curl -sI https://trejon.smallshire.co.uk/status            # 200, unchanged
```

A fuller checklist is in `AutoDeploy/patches/README.md`.

Then log in through Discord and confirm `/shop`, `/credits` and `/gigs` load, and that
`/gigs` returns results rather than a Skiddle config error.

Check the bot log for `Webapp listening on 0.0.0.0:8090` and, if auth env is missing,
`Webapp auth not configured`.

Note `/bot/` itself returns 404 — the deployer only serves `/webhook` and `/restart`, so
`/bot/` hitting nothing is expected, not a fault.

## Notes

- `--remove-orphans` in `AutoDeploy/update.sh` deletes containers for services no longer in
  the compose file, so the first deploy after `bot-web-server` is removed deletes that
  container. It is scoped to the `autorun-iter8-bot` project, so the public proxy is
  untouched by a deploy.
- `AutoDeploy/update.sh` runs `git reset --hard origin/main`, so only committed work on
  `main` is deployed. It does not `git clean`, so untracked files in the clone persist.
- The deployer runs `update.sh` on its own startup as well as on each push to `main`, so
  restarting it also triggers a deploy. `GET /restart` (behind `/bot/restart`) re-runs it.
- The deployer image is Python 3.14; the bot image is Python 3.11. Both fine as-is.