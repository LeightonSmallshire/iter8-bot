# Host-side patches

Changes that have to be applied outside this repo. Neither is applied by the deploy
pipeline, and neither is a git remote — they are diffs/snippets to apply by hand on
machines you cannot reach from CI.

| File | Target | Machine |
| --- | --- | --- |
| `nginx-bitmmo-root-target.patch` | the public reverse proxy's `nginx.conf` | `zero` (`/home/zero/CLionProjects/BitMMO-5`) |
| `app-env-webapp.add` | `/app/data/webapp.env` on the Pi (shared `iter8-bot-data` volume) | any, once |

The Discord redirect URI is the third piece and lives in the Discord developer portal,
not on either machine:

```
https://trejon.smallshire.co.uk/auth/callback
```

## nginx-bitmmo-root-target.patch

Two changes to the public proxy's config:

1. The `botweb_backend` upstream moves from `bot-web-server:80` to `iter8-bot-runner:8090`.
   The intermediate nginx container (`bot-web-server`) was removed from
   `docker-compose.yml`, so its name stops resolving on the next deploy. The bot serves
   the webapp and the legacy static pages directly now.
2. A `location /` block, so the webapp is reachable at the domain root. The webapp emits
   root-absolute URLs (`/static/…`, `/shop`, `/api/…`, `/auth/…`), so a path prefix will
   not work. Nginx matches the longest prefix, so `/bot/`, `/botweb/`, `/scratch/` and
   `/status` keep winning.

Apply it inside the BitMMO-5 project directory:

```bash
cp nginx.conf nginx.conf.bak
patch -p1 --dry-run < path/to/nginx-bitmmo-root-target.patch   # check first
patch -p1 < path/to/nginx-bitmmo-root-target.patch
nginx -t && nginx -s reload
```

The patch was generated against the config as it was actually running
(`/etc/nginx/nginx.conf` inside the `nginx-proxy` container) and has been verified to
apply cleanly and pass `nginx -t`. It assumes the source file still matches that
revision; if the proxy config has been edited since, apply the two changes by hand
instead of fighting the patch.

**Why it is a patch and not an edit:** that config is baked into the `bitmmo-5-nginx-proxy`
image (`COPY ./config/ /etc/nginx/`), not bind-mounted. Editing the file inside the
running container works, but the change is silently lost the next time the proxy image is
rebuilt. Better long-term fix: bind-mount a conf over `/etc/nginx/nginx.conf` in the
BitMMO-5 compose file so this repo's copy is the source of truth.

## app-env-webapp.add

The six `WEBAPP_*`/`SKIDDLE_*`/`DISCORD_CLIENT_*` keys the webapp needs.

Write them to `/app/data/webapp.env`, which is the shared `iter8-bot-data` volume that
both the deployer and the bot container mount. Do **not** try to edit `/app/.env`: it is
baked into the `autodeploy-iter8-deployer` image and the container's root filesystem is
read-only, so the write fails with `Read-only file system`.

`docker-compose.yml` declares it as a second, optional `env_file`, so a machine without
the file still deploys cleanly:

```yaml
env_file:
  - ../.env
  - path: /app/data/webapp.env
    required: false
```

Until this file exists, the bot boots normally and every Discord feature works, but `/`
and every `/api/*` redirect to `/auth/login`, which returns **503 Login is not configured
yet.**

## Order of operations

The bot must be redeployed before the nginx patch lands. Pointing `location /` at a bot
that has not yet been recreated with the webapp serving gives a 404, and if
`bot-web-server` is already deleted the upstream does not resolve at all.

1. Write the env file to `/app/data/webapp.env` on the Pi.
2. Merge this branch to `main` and let the webhook deploy it.
3. Confirm success in the deployer's Discord webhook channel.
4. Apply the nginx patch and reload.

## Verifying afterwards

```bash
curl -sI https://trejon.smallshire.co.uk/           # 200, the login page
curl -s  https://trejon.smallshire.co.uk/healthz    # {"status":"ok"}
curl -sI https://trejon.smallshire.co.uk/static/shop.css  # 200
curl -sI https://trejon.smallshire.co.uk/go.html    # 200, legacy page
curl -sI https://trejon.smallshire.co.uk/legacy/    # 200, legacy directory
curl -sI https://trejon.smallshire.co.uk/botweb/    # 200, legacy alias still up
curl -sI https://trejon.smallshire.co.uk/status     # 200, unchanged
```

Then log in through Discord and confirm `/shop`, `/credits` and `/gigs` load, and that
`/gigs` returns results rather than a Skiddle config error.